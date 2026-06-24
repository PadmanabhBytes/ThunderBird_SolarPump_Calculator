"""
Pump pre-filter service — applies compatibility rules before performance evaluation.

Filter rules (spec Section 4)
------------------------------
1. Casing size
   - casing < 3.5"  → exclude ALL pumps (no compatible design exists)
   - casing < 4.5"  → exclude pumps requiring ≥ 4" casing (min_casing_diameter_in >= 4.0)

2. Generator / grid backup
   - generator_required=True → exclude DC-only pumps
   - Exception: if removing DC-only pumps leaves zero eligible pumps,
     the filter is relaxed and a warning is issued.

3. Water quality
   - poor_water_quality=True → exclude HELICAL_ROTOR pump type

4. Region restriction (helical)
   - Helical rotor pumps may be restricted in certain geographic regions.
   - Scaffold: currently accepts a ``region_restricts_helical`` flag.
     When a full geo-lookup dataset is integrated, this flag will be derived
     from lat/long data instead.

All filters return the filtered list plus a list of human-readable reason strings
so the caller (controller) can include them in the response warnings.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..models.pump import Pump, PumpType, VoltageClass

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Result of the pre-filter pass."""
    pumps: List[Pump]
    excluded_count: int
    reasons: List[str] = field(default_factory=list)
    hard_stop: bool = False       # True when casing < 3.5" → no pumps can be installed


# Recovery rate thresholds per TBS pump category (Section 10.7 of client requirements)
_RECOVERY_THRESHOLD = {
    "A": lambda gpm, rec: gpm <= rec * 2.4,   # External Drive
    "B": lambda gpm, rec: gpm <= rec + 2.5,   # Internal Drive (stacked impeller)
    "C": lambda gpm, rec: gpm <= rec,          # Helical Rotor
}


class PumpFilterService:
    """
    Applies compatibility pre-filters to the full pump catalog.

    Call ``filter_pumps()`` before passing pumps to ``PumpEvalService``.
    """

    def filter_pumps(
        self,
        pumps: List[Pump],
        well_casing_diameter_in: Optional[float] = None,
        generator_backup_required: bool = False,
        poor_water_quality: bool = False,
        region_restricts_helical: bool = False,
        recovery_rate_gpm: Optional[float] = None,
        operating_gpm: Optional[float] = None,
    ) -> FilterResult:
        """
        Apply all compatibility rules and return the surviving pump list.

        Args:
            pumps:                    Full catalog pump list.
            well_casing_diameter_in:  Inner casing diameter (inches), or None if unknown.
            generator_backup_required: True → exclude DC-only pumps.
            poor_water_quality:        True → exclude helical rotor pumps.
            region_restricts_helical:  True → exclude helical rotor pumps (geographic rule).

        Returns:
            FilterResult with filtered pump list, exclusion count, and reason strings.
        """
        reasons: List[str] = []
        original_count = len(pumps)
        filtered = list(pumps)

        # ── Rule 1: casing size ───────────────────────────────────────────────
        if well_casing_diameter_in is not None:
            if well_casing_diameter_in < 3.5:
                logger.warning(
                    "Casing %.2f\" < 3.5\" — no pumps compatible.", well_casing_diameter_in
                )
                return FilterResult(
                    pumps=[],
                    excluded_count=original_count,
                    reasons=[
                        f"Well casing ({well_casing_diameter_in:.2f}\") is smaller than 3.5\". "
                        "No standard submersible pump design is compatible. "
                        "Verify casing diameter before proceeding."
                    ],
                    hard_stop=True,
                )

            # Warning for exactly 4" casing — pump fits but clearance is tight
            if 4.0 <= well_casing_diameter_in < 4.5:
                reasons.append(
                    "Warning: 4\" well casing selected with an AC/DC 4\" pump option. "
                    "Ensure the actual inner casing diameter meets minimum clearance "
                    "requirements for the selected pump before installation."
                )

            if well_casing_diameter_in < 4.5:
                before = len(filtered)
                filtered = [p for p in filtered if p.min_casing_diameter_in <= well_casing_diameter_in]
                removed = before - len(filtered)
                if removed:
                    reasons.append(
                        f"Excluded {removed} pump(s) requiring ≥4\" casing "
                        f"(well casing = {well_casing_diameter_in:.2f}\")."
                    )
                    logger.info(
                        "Casing filter: removed %d pump(s) needing ≥4\" from %d total.",
                        removed, before,
                    )

        # ── Rule 2: water quality → exclude helical rotor ─────────────────────
        if poor_water_quality:
            before = len(filtered)
            filtered = [
                p for p in filtered
                if p.pump_type != PumpType.HELICAL_ROTOR
            ]
            removed = before - len(filtered)
            if removed:
                reasons.append(
                    f"Excluded {removed} helical rotor pump(s) — "
                    "poor water quality (solids/sand/iron bacteria) reported."
                )
                logger.info("Water quality filter: removed %d helical rotor pump(s).", removed)

        # ── Rule 3: region restriction → exclude helical rotor ────────────────
        if region_restricts_helical and not poor_water_quality:
            before = len(filtered)
            filtered = [
                p for p in filtered
                if p.pump_type != PumpType.HELICAL_ROTOR
            ]
            removed = before - len(filtered)
            if removed:
                reasons.append(
                    f"Excluded {removed} helical rotor pump(s) — "
                    "helical rotor pumps are restricted in this region."
                )
                logger.info("Region filter: removed %d helical rotor pump(s).", removed)

        # ── Rule 4: generator/grid backup → exclude DC-only ───────────────────
        if generator_backup_required:
            filtered, dc_reasons = self._apply_generator_filter(filtered)
            reasons.extend(dc_reasons)

        # ── Rule 5: recovery rate → per-category threshold filter ────────────
        if recovery_rate_gpm is not None and operating_gpm is not None:
            filtered, rec_reasons = self._apply_recovery_filter(
                filtered, operating_gpm, recovery_rate_gpm
            )
            reasons.extend(rec_reasons)

        excluded_count = original_count - len(filtered)
        logger.info(
            "PumpFilterService: %d → %d pumps after pre-filtering (%d excluded).",
            original_count, len(filtered), excluded_count,
        )

        return FilterResult(
            pumps=filtered,
            excluded_count=excluded_count,
            reasons=reasons,
        )

    @staticmethod
    def _apply_generator_filter(pumps: List[Pump]) -> Tuple[List[Pump], List[str]]:
        """
        Remove DC-only pumps when generator/grid backup is required.

        Relaxes the filter (with a warning) if removing DC pumps leaves
        no candidates — avoids returning an empty set when DC is the only option.
        """
        reasons: List[str] = []
        ac_compatible = [
            p for p in pumps
            if p.voltage_class != VoltageClass.DC
        ]

        if not ac_compatible and pumps:
            reasons.append(
                "Generator/grid backup is required, but no AC-compatible pumps "
                "are in the catalog. DC pumps retained as the only available option. "
                "Verify pump compatibility with the planned backup system."
            )
            logger.warning(
                "Generator filter relaxed — no AC pumps available; keeping %d DC pump(s).",
                len(pumps),
            )
            return pumps, reasons

        removed = len(pumps) - len(ac_compatible)
        if removed:
            reasons.append(
                f"Excluded {removed} DC-only pump(s) — generator/grid backup required."
            )
            logger.info("Generator filter: removed %d DC-only pump(s).", removed)

        return ac_compatible, reasons

    @staticmethod
    def _apply_recovery_filter(
        pumps: List[Pump],
        operating_gpm: float,
        recovery_rate_gpm: float,
    ) -> Tuple[List[Pump], List[str]]:
        """
        Exclude pumps whose operating GPM exceeds the per-category recovery threshold.

        Category A (External Drive):  operating_gpm ≤ recovery × 2.4
        Category B (Internal Drive):  operating_gpm ≤ recovery + 2.5
        Category C (Helical Rotor):   operating_gpm ≤ recovery

        Pumps without a known category are always kept.
        If every pump fails the filter, all are retained with a warning
        (same relaxation pattern as the generator filter).
        """
        reasons: List[str] = []
        passing = [
            p for p in pumps
            if p.pump_category is None
            or p.pump_category not in _RECOVERY_THRESHOLD
            or _RECOVERY_THRESHOLD[p.pump_category](operating_gpm, recovery_rate_gpm)
        ]

        if not passing and pumps:
            reasons.append(
                f"Recovery rate filter relaxed — no pumps pass the per-category "
                f"threshold at {operating_gpm:.1f} GPM / {recovery_rate_gpm:.1f} GPM recovery. "
                "Verify well recovery characteristics before installation."
            )
            logger.warning(
                "Recovery filter relaxed — all %d pump(s) exceeded threshold; retaining all.",
                len(pumps),
            )
            return pumps, reasons

        removed = len(pumps) - len(passing)
        if removed:
            reasons.append(
                f"Excluded {removed} pump(s) — operating GPM ({operating_gpm:.1f}) "
                f"exceeds the per-category recovery threshold "
                f"(well recovery {recovery_rate_gpm:.1f} GPM)."
            )
            logger.info(
                "Recovery filter: removed %d pump(s) at %.1f GPM / %.1f GPM recovery.",
                removed, operating_gpm, recovery_rate_gpm,
            )

        return passing, reasons
