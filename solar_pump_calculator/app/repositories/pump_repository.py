"""
Pump repository — catalog metadata + performance dataset loading.

Directory layout expected under ``settings.pump_data_path.parent``:

    data/pumps/
    ├── pump_catalog.csv              ← one row per SKU (identity + envelope)
    └── performance/
        ├── SCHEMA.md                 ← format documentation for engineers
        ├── _template.csv             ← blank template for new datasets
        └── <pump_id>.csv             ← one file per pump with real data

Performance CSV format
----------------------
    head_ft, <watts_1>, <watts_2>, ..., <watts_n>
    16.4,    0.0,       2.3,       ..., 9.5
    46.5,    0.0,       1.8,       ..., 8.4
    ...

Rules:
  - Column ``head_ft``  : operating head in US feet (float, ascending, required).
  - Remaining columns   : each header is a power level in watts (numeric string).
  - Cell values         : achievable flow in US GPM at that (head, power) point.
  - GPM must be ≥ 0.  Zero means the pump cannot move water at that condition.
  - Rows are sorted ascending by head before use; out-of-order rows are fixed.
  - At least 2 head rows and 1 power column are required.
  - Power levels must be > 0 W.
  - Lines beginning with ``#`` are treated as comments and ignored.

Validation warnings (not errors) are emitted for:
  - GPM that increases with head in a given power column.
  - Duplicate head rows.
  - Power levels ≤ 0 W.
  - Negative GPM values.

Startup sequence
----------------
    repo = PumpRepository(data_path=Path("data/pumps/pump_catalog.csv"))
    repo.load()
    # Repositories are then stored on app.state and injected via Depends.

Public interface
----------------
    get_all_pumps()                         → List[Pump]
    get_pump_by_id(pump_id)                 → Pump
    get_performance_curve(pump_id)          → Optional[PerformanceCurve]
    has_performance_curve(pump_id)          → bool
    get_pumps_by_type(pump_type)            → List[Pump]
    get_pumps_in_range(min_flow, min_head)  → List[Pump]
    pump_count()                            → int
    performance_curve_count()               → int
    get_available_pump_ids()                → List[str]

DB-migration note
-----------------
Replace ``_load_catalog`` and ``_load_performance_dir`` with ORM queries that
return the same typed structures.  The public interface is unchanged.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from ..models.pump import Pump, PumpType, VoltageClass
from ..utils.exceptions import DataLoadError, DataNotFoundError

logger = logging.getLogger(__name__)


# ── Performance curve dataclass ───────────────────────────────────────────────

@dataclass
class PerformanceCurve:
    """
    Head-vs-GPM lookup table at multiple power levels for a single pump SKU.

    Attributes
    ----------
    pump_id : str
        Matches the ``pump_id`` field in ``pump_catalog.csv`` and the stem of
        the performance CSV filename.
    power_levels_w : List[float]
        Distinct power breakpoints in watts, sorted ascending.
        These are the column headers of the source CSV (numeric strings).
    head_rows_ft : List[float]
        Distinct head breakpoints in feet, sorted ascending.
        These are the values in the ``head_ft`` column of the source CSV.
    gpm_matrix : List[List[float]]
        Two-dimensional lookup table.
        Outer index  → head_rows_ft index (row).
        Inner index  → power_levels_w index (column).
        gpm_matrix[i][j] = achievable GPM at head_rows_ft[i] and power_levels_w[j].
    source_path : Path
        Filesystem path the curve was loaded from.  Useful for error messages.
    """
    pump_id:        str
    power_levels_w: List[float]
    head_rows_ft:   List[float]
    gpm_matrix:     List[List[float]]
    source_path:    Path = field(default_factory=Path)

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def min_head_ft(self) -> float:
        """Smallest head breakpoint in the dataset (ft)."""
        return self.head_rows_ft[0]

    @property
    def max_head_ft(self) -> float:
        """Largest head breakpoint in the dataset (ft)."""
        return self.head_rows_ft[-1]

    @property
    def min_power_w(self) -> float:
        """Smallest power level in the dataset (W)."""
        return self.power_levels_w[0]

    @property
    def max_power_w(self) -> float:
        """Largest power level in the dataset (W)."""
        return self.power_levels_w[-1]

    @property
    def max_gpm_at_min_head(self) -> float:
        """Maximum achievable GPM across all power levels at the lowest head."""
        return max(self.gpm_matrix[0]) if self.gpm_matrix else 0.0

    def gpm_column(self, power_col_idx: int) -> List[float]:
        """Return all GPM values for one power column (ordered by head ascending)."""
        return [row[power_col_idx] for row in self.gpm_matrix]


# ── Dataset validation ────────────────────────────────────────────────────────

class PumpDatasetValidator:
    """
    Validates a parsed PerformanceCurve and emits structured warnings.

    All issues are logged; none raise exceptions so that a partially-valid
    dataset can still be used for pumps whose data rows are clean.

    Usage::

        warnings = PumpDatasetValidator.validate(curve, source_name)
        # warnings is a List[str] — empty means clean dataset
    """

    @staticmethod
    def validate(curve: PerformanceCurve, source: str) -> List[str]:
        """
        Run all validation checks and return a list of warning strings.

        Args:
            curve:  Parsed PerformanceCurve object.
            source: Human-readable name for log messages (usually filename).

        Returns:
            List[str] — one entry per issue found.  Empty = clean.
        """
        warnings: List[str] = []

        # 1. Minimum shape requirements
        if len(curve.head_rows_ft) < 2:
            msg = f"{source}: fewer than 2 head rows — interpolation not possible"
            logger.warning(msg)
            warnings.append(msg)

        if len(curve.power_levels_w) < 1:
            msg = f"{source}: no power-level columns found"
            logger.error(msg)
            warnings.append(msg)

        # 2. Duplicate head rows
        if len(set(curve.head_rows_ft)) != len(curve.head_rows_ft):
            msg = f"{source}: duplicate head_ft values detected"
            logger.warning(msg)
            warnings.append(msg)

        # 3. Non-positive power levels
        for pw in curve.power_levels_w:
            if pw <= 0:
                msg = f"{source}: non-positive power level {pw:.1f} W — must be > 0"
                logger.warning(msg)
                warnings.append(msg)

        # 4. Negative GPM values
        for row_idx, row in enumerate(curve.gpm_matrix):
            for col_idx, gpm in enumerate(row):
                if gpm < 0:
                    msg = (
                        f"{source}: negative GPM ({gpm:.2f}) at "
                        f"head={curve.head_rows_ft[row_idx]:.1f} ft, "
                        f"power={curve.power_levels_w[col_idx]:.0f} W"
                    )
                    logger.warning(msg)
                    warnings.append(msg)

        # 5. GPM should not increase as head increases (for a given power column)
        #    A tolerance of 0.5 GPM is allowed for measurement noise.
        for col_idx, power_w in enumerate(curve.power_levels_w):
            col_gpms = curve.gpm_column(col_idx)
            for i in range(1, len(col_gpms)):
                if col_gpms[i] > col_gpms[i - 1] + 0.5:
                    msg = (
                        f"{source}: GPM increases with head at {power_w:.0f} W "
                        f"(head {curve.head_rows_ft[i - 1]:.1f} ft → "
                        f"{curve.head_rows_ft[i]:.1f} ft, "
                        f"GPM {col_gpms[i - 1]:.2f} → {col_gpms[i]:.2f}) — "
                        "verify dataset"
                    )
                    logger.warning(msg)
                    warnings.append(msg)
                    break  # one warning per column is sufficient

        # 6. GPM should generally increase with power at a fixed head
        for row_idx, head_ft in enumerate(curve.head_rows_ft):
            row_gpms = curve.gpm_matrix[row_idx]
            for j in range(1, len(row_gpms)):
                if row_gpms[j] < row_gpms[j - 1] - 0.5:
                    msg = (
                        f"{source}: GPM decreases with power at {head_ft:.1f} ft "
                        f"({curve.power_levels_w[j - 1]:.0f} W → "
                        f"{curve.power_levels_w[j]:.0f} W, "
                        f"GPM {row_gpms[j - 1]:.2f} → {row_gpms[j]:.2f}) — "
                        "verify dataset"
                    )
                    logger.warning(msg)
                    warnings.append(msg)
                    break  # one per row

        return warnings


# ── Repository ────────────────────────────────────────────────────────────────

class PumpRepository:
    """
    In-memory store for the pump catalog and performance datasets.

    Args:
        data_path: Absolute path to ``pump_catalog.csv``.
                   Performance CSVs are expected in a ``performance/``
                   subdirectory alongside the catalog file.
    """

    def __init__(self, data_path: Path) -> None:
        self._data_path:     Path = data_path
        self._perf_dir:      Path = data_path.parent / "performance"
        self._pumps:         List[Pump]                    = []
        self._index:         Dict[str, Pump]               = {}
        self._curves:        Dict[str, PerformanceCurve]   = {}
        self._load_warnings: Dict[str, List[str]]          = {}   # pump_id → warnings
        self._loaded:        bool                          = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Load pump catalog + all performance datasets from disk.

        Call once at application startup (via lifespan).
        """
        self._load_catalog()
        self._load_performance_dir()
        self._loaded = True
        logger.info(
            "PumpRepository ready: %d pumps in catalog, %d with performance datasets",
            len(self._pumps), len(self._curves),
        )
        if self._curves:
            logger.info(
                "Performance datasets loaded for: %s",
                ", ".join(sorted(self._curves)),
            )
        else:
            logger.info(
                "No performance datasets found in %s — "
                "all evaluations will use catalog envelope bounds. "
                "Add real datasets to enable curve-based evaluation.",
                self._perf_dir,
            )

    # ── Private: catalog ──────────────────────────────────────────────────────

    def _load_catalog(self) -> None:
        try:
            df = pd.read_csv(self._data_path, comment="#")
            df.columns = df.columns.str.strip().str.lower()
        except FileNotFoundError as exc:
            raise DataLoadError(
                f"Pump catalog not found: {self._data_path}"
            ) from exc
        except Exception as exc:
            raise DataLoadError(
                f"Failed to read pump catalog '{self._data_path}': {exc}"
            ) from exc

        pumps:  List[Pump] = []
        errors: List[str]  = []

        for idx, row in df.iterrows():
            try:
                pumps.append(self._row_to_pump(row))
            except Exception as exc:
                errors.append(f"Row {idx} (pump_id={row.get('pump_id', '?')}): {exc}")

        if errors:
            logger.warning(
                "PumpRepository: %d catalog row(s) skipped:\n  %s",
                len(errors), "\n  ".join(errors),
            )

        if not pumps:
            raise DataLoadError(
                f"Pump catalog at '{self._data_path}' contained no valid rows."
            )

        self._pumps = pumps
        self._index = {p.pump_id: p for p in pumps}
        logger.info(
            "PumpRepository: loaded %d pumps from catalog '%s'",
            len(pumps), self._data_path.name,
        )

    def _row_to_pump(self, row: "pd.Series") -> Pump:  # type: ignore[type-arg]
        """Parse a single catalog CSV row into a Pump instance."""

        def _opt_float(val: object) -> Optional[float]:
            return float(val) if pd.notna(val) else None  # type: ignore[arg-type]

        def _opt_str(val: object) -> Optional[str]:
            s = str(val).strip() if pd.notna(val) else None  # type: ignore[arg-type]
            return s if s not in ("", "nan", "None") else None

        def _bool_col(val: object, default: bool = False) -> bool:
            if pd.isna(val):  # type: ignore[arg-type]
                return default
            s = str(val).strip().lower()
            return s in ("1", "true", "yes", "y")

        # Voltage class can be overridden from the catalog
        raw_vc = _opt_str(row.get("voltage_class"))
        try:
            vc = VoltageClass(raw_vc.lower()) if raw_vc else VoltageClass.UNKNOWN
        except ValueError:
            vc = VoltageClass.UNKNOWN

        return Pump(
            pump_id=str(row["pump_id"]).strip(),
            brand=str(row["brand"]).strip(),
            model=str(row["model"]).strip(),
            pump_type=PumpType(str(row["type"]).strip().lower()),
            min_flow_gpm=float(row["min_flow_gpm"]),
            max_flow_gpm=float(row["max_flow_gpm"]),
            min_head_ft=float(row["min_head_ft"]),
            max_head_ft=float(row["max_head_ft"]),
            rated_power_w=float(row["rated_power_w"]),
            voltage_range=str(row["voltage_v"]).strip(),
            voltage_class=vc,
            efficiency_percent=float(row["efficiency_percent"]),
            requires_inverter=_bool_col(row.get("requires_inverter"), default=False),
            mppt_compatible=_bool_col(row.get("mppt_compatible"), default=False),
            price_usd=_opt_float(row.get("price_usd")),
            description=_opt_str(row.get("description")),
            rated_flow_gpm=_opt_float(row.get("rated_flow_gpm")),
        )

    # ── Private: performance datasets ─────────────────────────────────────────

    def _load_performance_dir(self) -> None:
        """
        Scan ``performance/`` for per-pump CSV files and load each one.

        Files whose stem starts with ``_`` (e.g. ``_template.csv``) are skipped.
        Parse failures are logged as warnings; they do not abort startup.
        """
        if not self._perf_dir.is_dir():
            logger.info(
                "Performance directory '%s' does not exist — "
                "create it and add <pump_id>.csv files when real datasets are available.",
                self._perf_dir,
            )
            return

        loaded  = 0
        skipped = 0
        for csv_path in sorted(self._perf_dir.glob("*.csv")):
            if csv_path.stem.startswith("_"):
                continue  # skip templates / internal files

            pump_id = csv_path.stem

            if pump_id not in self._index:
                logger.warning(
                    "Performance file '%s' has no matching pump_id in catalog — skipped",
                    csv_path.name,
                )
                skipped += 1
                continue

            try:
                curve = self._parse_performance_csv(pump_id, csv_path)
                warnings = PumpDatasetValidator.validate(curve, csv_path.name)
                self._curves[pump_id] = curve
                if warnings:
                    self._load_warnings[pump_id] = warnings
                loaded += 1
            except Exception as exc:
                logger.warning(
                    "Skipping performance file '%s': %s",
                    csv_path.name, exc,
                )
                skipped += 1

        logger.info(
            "Performance datasets: %d loaded, %d skipped (see warnings above)",
            loaded, skipped,
        )

    def _parse_performance_csv(
        self,
        pump_id: str,
        path: Path,
    ) -> PerformanceCurve:
        """
        Parse a performance CSV into a PerformanceCurve.

        Expected format::

            head_ft, <watts_1>, <watts_2>, ..., <watts_n>
            16.4,    4.8,       6.12,      ..., 9.28
            46.5,    4.35,      5.55,      ..., 8.42
            ...

        Args:
            pump_id: Expected pump identifier (used in error messages).
            path:    CSV file path.

        Returns:
            Parsed and sorted PerformanceCurve.

        Raises:
            ValueError: For any structural problem (missing columns, non-numeric
                        headers, empty data, etc.).
        """
        try:
            df = pd.read_csv(path, comment="#")
        except Exception as exc:
            raise ValueError(f"Cannot read CSV: {exc}") from exc

        df.columns = df.columns.str.strip()

        if "head_ft" not in df.columns:
            raise ValueError(
                f"Missing required 'head_ft' column. "
                f"Expected format: head_ft,<watts_1>,<watts_2>,... "
                f"Got columns: {list(df.columns)}"
            )

        power_col_strs = [c for c in df.columns if c != "head_ft"]
        if not power_col_strs:
            raise ValueError(
                "No power-level columns found (expected numeric watt headers)."
            )

        # Validate that all power column headers are numeric
        try:
            ordered_cols  = sorted(power_col_strs, key=float)
            power_levels  = [float(c) for c in ordered_cols]
        except ValueError as exc:
            raise ValueError(
                f"Non-numeric power column header: {exc}. "
                "Column headers must be watt values (e.g. 100, 200, 400)."
            ) from exc

        # Drop rows where head_ft is missing
        df = df.dropna(subset=["head_ft"])
        if df.empty:
            raise ValueError("No valid data rows found (all head_ft values are missing).")

        if len(df) < 2:
            raise ValueError(
                f"Only {len(df)} head row(s) found; at least 2 are required for interpolation."
            )

        # Sort ascending by head
        df = df.sort_values("head_ft").reset_index(drop=True)

        head_rows  = [float(v) for v in df["head_ft"]]
        gpm_matrix: List[List[float]] = []

        for _, row in df.iterrows():
            gpm_row: List[float] = []
            for col in ordered_cols:
                raw = row[col]
                if pd.isna(raw):
                    raise ValueError(
                        f"Missing GPM value at head_ft={row['head_ft']}, "
                        f"power_col={col} W. Fill all cells or use 0.0 for no-flow conditions."
                    )
                gpm_val = float(raw)
                if gpm_val < 0:
                    raise ValueError(
                        f"Negative GPM ({gpm_val}) at head_ft={row['head_ft']}, "
                        f"power_col={col} W. Use 0.0 to represent no-flow."
                    )
                gpm_row.append(gpm_val)
            gpm_matrix.append(gpm_row)

        return PerformanceCurve(
            pump_id=pump_id,
            power_levels_w=power_levels,
            head_rows_ft=head_rows,
            gpm_matrix=gpm_matrix,
            source_path=path,
        )

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    # ── Catalog queries ───────────────────────────────────────────────────────

    def get_all_pumps(self) -> List[Pump]:
        """Return a copy of the full pump list."""
        self._ensure_loaded()
        return list(self._pumps)

    def get_pump_by_id(self, pump_id: str) -> Pump:
        """
        Return the pump with the given ID.

        Raises:
            DataNotFoundError: If pump_id is not in the catalog.
        """
        self._ensure_loaded()
        pump = self._index.get(pump_id)
        if pump is None:
            available = sorted(self._index)
            raise DataNotFoundError(
                f"Pump '{pump_id}' not found in catalog. "
                f"Available IDs: {available}"
            )
        return pump

    def get_pumps_by_type(self, pump_type: PumpType) -> List[Pump]:
        """Return all pumps matching a pump type."""
        self._ensure_loaded()
        return [p for p in self._pumps if p.pump_type == pump_type]

    def get_pumps_in_range(
        self,
        min_flow_gpm: float,
        min_head_ft: float,
    ) -> List[Pump]:
        """
        Return pumps whose catalog envelope covers the given flow and head.

        This is a pre-filter based on catalog bounds, not curve-based evaluation.
        Use ``PumpEvalService`` for accurate operating-point analysis.
        """
        self._ensure_loaded()
        return [
            p for p in self._pumps
            if p.max_flow_gpm >= min_flow_gpm and p.max_head_ft >= min_head_ft
        ]

    def get_available_pump_ids(self) -> List[str]:
        """Return sorted list of all pump_id values in the catalog."""
        self._ensure_loaded()
        return sorted(self._index)

    def pump_count(self) -> int:
        """Number of pumps in the catalog."""
        self._ensure_loaded()
        return len(self._pumps)

    # ── Performance curve queries ─────────────────────────────────────────────

    def get_performance_curve(self, pump_id: str) -> Optional[PerformanceCurve]:
        """
        Return the performance dataset for the given pump, or None.

        None means no CSV was found in ``performance/`` for this pump_id.
        Callers should fall back to catalog envelope evaluation in that case.
        """
        self._ensure_loaded()
        return self._curves.get(pump_id)

    def has_performance_curve(self, pump_id: str) -> bool:
        """True if a validated performance dataset is loaded for this pump."""
        self._ensure_loaded()
        return pump_id in self._curves

    def performance_curve_count(self) -> int:
        """Number of pumps that have a loaded performance dataset."""
        self._ensure_loaded()
        return len(self._curves)

    def get_load_warnings(self, pump_id: str) -> List[str]:
        """
        Return any data-quality warnings emitted during dataset loading.

        Returns an empty list if the pump has no warnings or no dataset.
        """
        self._ensure_loaded()
        return list(self._load_warnings.get(pump_id, []))

    @property
    def is_loaded(self) -> bool:
        return self._loaded
