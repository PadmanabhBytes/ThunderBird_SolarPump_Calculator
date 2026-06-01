"""
Pump ranking service — three-category recommendation engine.

Categories
----------
ECONOMICAL  Minimum viable system. Selects the pump requiring the fewest solar
            panels. Tie-breaks on rated power (lower) then price (lower).

PRECISE     Closest production match. Selects the pump whose operating power
            most closely matches what the solar array produces at the design
            point. Rewards balanced power utilisation and ideal head margin.

PREMIUM     Highest reliability and production confidence. Rewards high BEP
            efficiency and generous head/flow margin. Applies a submersible
            (stacked impeller) preference: if the highest-scoring submersible
            is within CategoryConfig.submersible_panel_tolerance panels of the
            highest-scoring non-submersible, the submersible is selected.

Pipeline
--------
    1. Pre-filter: keep only eligible pumps (meets_head AND meets_flow).
    2. Solar size each eligible pump individually (curve-based watts when
       available; hydraulic-estimate watts otherwise).
    3. Score each pump per category using the configured ScoringWeights.
    4. Select the winner for each category (with Premium submersible rule).
    5. Validate the result set; emit warnings for empty category slots.
    6. Return RankedRecommendationSet.

Extensibility
-------------
    - Add a new scoring dimension: add it to ScoringWeights, implement the
      sub-scorer, and include it in _composite_score().
    - Add a new filter (AC/DC preference, pump type): implement a filter
      function and call it in _apply_preference_filters() [stub below].
    - Override the default config: pass a custom RankingConfig to rank().
"""

import logging
from typing import Callable, List, Optional, Tuple

from ..models.pump import PumpType
from ..models.recommendation import (
    CategorizedRecommendation,
    CategoryConfig,
    RankedRecommendationSet,
    RankingConfig,
    RankingValidationResult,
    RecommendationCategory,
    ScoringWeights,
)
from ..services.pump_eval_service import PumpEvalResult, PumpEvalService
from ..services.solar_service import SolarService

logger = logging.getLogger(__name__)

# STC derating applied to raw GPM for display (matches PDF "7.5% efficiency loss from STC")
_DISPLAY_STC_LOSS: float = 0.075

# Normalisation constants (engineering bounds, not data)
_EFF_MIN_PCT:     float = 30.0   # lower bound for efficiency normalisation
_EFF_MAX_PCT:     float = 70.0   # upper bound for efficiency normalisation
_IDEAL_HM_LOW:    float = 0.10   # ideal head margin lower bound (fraction)
_IDEAL_HM_HIGH:   float = 0.30   # ideal head margin upper bound (fraction)
_BEP_RATIO_LOW:   float = 0.70   # ideal power-match ratio lower bound
_BEP_RATIO_HIGH:  float = 0.90   # ideal power-match ratio upper bound


# ── Scored candidate (internal) ───────────────────────────────────────────────

class _ScoredCandidate:
    """Internal representation of a scored eligible pump."""
    __slots__ = (
        "result", "score", "op_watts", "dh_watts", "solar_panels",
        "solar_governing_path", "achievable_gpm",
    )

    def __init__(
        self,
        result:               PumpEvalResult,
        score:                float,
        op_watts:             float,
        dh_watts:             float,
        solar_panels:         int,
        solar_governing_path: str,
        achievable_gpm:       Optional[float] = None,
    ) -> None:
        self.result               = result
        self.score                = score
        self.op_watts             = op_watts
        self.dh_watts             = dh_watts
        self.solar_panels         = solar_panels
        self.solar_governing_path = solar_governing_path
        self.achievable_gpm       = achievable_gpm


# ── Service ───────────────────────────────────────────────────────────────────

class RankingService:
    """
    Three-category recommendation engine.

    Args:
        solar_service: Loaded :class:`SolarService` instance.
    """

    def __init__(self, solar_service: SolarService) -> None:
        self._solar = solar_service

    # ── Public interface ──────────────────────────────────────────────────────

    def rank(
        self,
        eval_results:             List[PumpEvalResult],
        required_flow_gpm:        float,
        required_head_ft:         float,
        fallback_operating_watts: float,
        panel_wattage_w:          float,
        solar_coefficient:        float                = 1.25,
        deadhead_watts:           Optional[float]      = None,
        pump_eval_service:        Optional["PumpEvalService"] = None,
        stc_efficiency_loss:      float                = 0.075,
        config:                   Optional[RankingConfig] = None,
        generator_backup_required: bool               = False,
        pump_rated_gpm_fallback:  Optional[float]     = None,
    ) -> RankedRecommendationSet:
        """
        Run the full three-category ranking pipeline.

        Args:
            eval_results:             Output of ``PumpEvalService.evaluate_all()``.
            required_flow_gpm:        Target flow rate (GPM).
            required_head_ft:         Required TDH (ft).
            fallback_operating_watts: Hydraulic-estimate watts — used when a pump
                                      has no performance dataset.
            panel_wattage_w:          Panel nameplate wattage (W).
            solar_coefficient:        Array oversizing factor.
            deadhead_watts:           Shutoff power (W); defaults to op_watts when None.
            config:                   Ranking configuration. Defaults to
                                      ``RankingConfig.default()`` when None.

        Returns:
            :class:`RankedRecommendationSet` with one winner per category.
        """
        cfg = config or RankingConfig.default()

        # ── Step 1: Pre-filter to eligible pumps only ──────────────────────
        # This tool sizes only Thunderbird's 15TBS-4C-AC pump.
        # When generator backup is required, the pump qualifies even if solar
        # alone cannot meet the full required_flow_gpm (AC fills the gap).
        TBS_PUMP_ID = "15TBS-4C-AC"
        eligible = [
            r for r in eval_results
            if r.pump.pump_id == TBS_PUMP_ID and (
                r.is_eligible or (
                    generator_backup_required
                    and r.pump.max_head_ft >= required_head_ft
                )
            )
        ]
        total    = len(eval_results)

        if not eligible:
            logger.warning(
                "RankingService: no eligible pumps for Q=%.1f GPM, H=%.2f ft",
                required_flow_gpm, required_head_ft,
            )
            return self._empty_result(total, 0)

        # ── Step 2: Solar-size each eligible pump ──────────────────────────
        candidates = self._build_candidates(
            eligible, fallback_operating_watts, deadhead_watts,
            solar_coefficient, panel_wattage_w,
            pump_eval_service=pump_eval_service,
            tdh_ft=required_head_ft,
            required_flow_gpm=required_flow_gpm,
            stc_efficiency_loss=stc_efficiency_loss,
            generator_backup_required=generator_backup_required,
            pump_rated_gpm_fallback=pump_rated_gpm_fallback,
        )

        # ── Steps 3–4: Score and select per category ───────────────────────
        economical = self._select_economical(candidates, cfg.economical)
        precise    = self._select_precise(
            candidates, cfg.precise, fallback_operating_watts, panel_wattage_w, solar_coefficient,
        )
        premium    = self._select_premium(candidates, cfg.premium)

        # ── Step 5: Validate ───────────────────────────────────────────────
        validation = self._validate(economical, precise, premium)

        filled = sum(1 for w in (economical, precise, premium) if w is not None)

        logger.info(
            "RankingService: %d/%d eligible | economical=%s precise=%s premium=%s",
            len(eligible), total,
            economical.pump.pump_id if economical else "—",
            precise.pump.pump_id    if precise    else "—",
            premium.pump.pump_id    if premium    else "—",
        )

        return RankedRecommendationSet(
            economical=economical,
            precise=precise,
            premium=premium,
            total_evaluated=total,
            eligible_count=len(eligible),
            categories_filled=filled,
            validation=validation,
        )

    # ── Step 2: build scored candidates ──────────────────────────────────────

    def _build_candidates(
        self,
        eligible:                 List[PumpEvalResult],
        fallback_watts:           float,
        deadhead_watts:           Optional[float],
        solar_coefficient:        float,
        panel_wattage_w:          float,
        pump_eval_service:        Optional["PumpEvalService"] = None,
        tdh_ft:                   float = 0.0,
        required_flow_gpm:        float = 0.0,
        stc_efficiency_loss:      float = 0.075,
        generator_backup_required: bool = False,
        pump_rated_gpm_fallback:  Optional[float] = None,
    ) -> List[_ScoredCandidate]:
        """Solar-size each eligible pump; collect into _ScoredCandidate objects.

        When generator_backup_required is True the solar array is sized using
        irradiance-adjusted effective panel wattage (panel_wattage_w ÷ solar_coefficient)
        and targets the pump's own nameplate flow (pump_rated_gpm_fallback) rather
        than the customer's required_flow_gpm, since AC power covers the gap.
        The displayed achievable GPM is computed at the FULL array wattage.
        """
        candidates: List[_ScoredCandidate] = []
        for result in eligible:
            achievable_gpm: Optional[float] = None

            # ── Curve-based bilinear sizing (preferred) ───────────────────
            if pump_eval_service is not None and tdh_ft > 0 and required_flow_gpm > 0:

                n_panels, raw_gpm = pump_eval_service.size_panels_for_pump(
                    pump_id=result.pump.pump_id,
                    tdh_ft=tdh_ft,
                    required_gpm=required_flow_gpm,
                    panel_wattage_w=panel_wattage_w,
                    stc_efficiency_loss=stc_efficiency_loss,
                )
                display_stc_loss = _DISPLAY_STC_LOSS  # 7.5% always

                if n_panels is not None:
                    op_w           = n_panels * panel_wattage_w
                    dh_w           = deadhead_watts if deadhead_watts is not None else op_w
                    achievable_gpm = round(raw_gpm * (1.0 - display_stc_loss), 1) if raw_gpm is not None else None
                    candidates.append(_ScoredCandidate(
                        result=result,
                        score=0.0,
                        op_watts=op_w,
                        dh_watts=dh_w,
                        solar_panels=n_panels,
                        solar_governing_path="curve_bilinear",
                        achievable_gpm=achievable_gpm,
                    ))
                    continue  # skip fallback path

            # ── Fallback: production/deadhead path (no curve available) ───
            op_w = (
                result.operating_wattage_w
                if result.operating_wattage_w is not None
                else fallback_watts
            )
            dh_w = deadhead_watts if deadhead_watts is not None else op_w

            sizing = self._solar.calculate(
                operating_watts=op_w,
                deadhead_watts=dh_w,
                solar_coefficient=solar_coefficient,
                panel_wattage_w=panel_wattage_w,
            )

            candidates.append(_ScoredCandidate(
                result=result,
                score=0.0,
                op_watts=op_w,
                dh_watts=dh_w,
                solar_panels=sizing.final_panels,
                solar_governing_path=sizing.governing_path,
                achievable_gpm=result.achievable_gpm,
            ))
        return candidates

    # ── Step 3–4: Category selectors ─────────────────────────────────────────

    def _select_economical(
        self,
        candidates: List[_ScoredCandidate],
        cfg:        CategoryConfig,
    ) -> Optional[CategorizedRecommendation]:
        """
        Select the Economical winner.

        Primary sort: fewest solar panels.
        Scoring weights from cfg.weights applied to break ties meaningfully.
        """
        scored = [
            (self._composite_score(c, cfg.weights), c)
            for c in candidates
        ]
        # Primary: fewer panels = better; secondary: higher composite score
        scored.sort(key=lambda t: (t[1].solar_panels, -t[0]))

        if not scored:
            return None

        _, winner = scored[0]
        score = self._composite_score(winner, cfg.weights)

        rationale = self._rationale_economical(winner, scored)
        return self._build_recommendation(
            winner, RecommendationCategory.ECONOMICAL, score, rationale,
        )

    def _select_precise(
        self,
        candidates:           List[_ScoredCandidate],
        cfg:                  CategoryConfig,
        fallback_watts:       float,
        panel_wattage_w:      float,
        solar_coefficient:    float,
    ) -> Optional[CategorizedRecommendation]:
        """
        Select the Precise winner.

        Primary dimension: power utilisation ratio — how close operating_watts
        is to the power the solar array actually delivers at the design point.
        Solar production at design = panel_count × panel_wattage × (1/solar_coeff).
        A ratio of 1.0 means perfect match; <1.0 means underutilised array;
        >1.0 means the array must work above its design point.

        Weights from cfg.weights applied for the full composite.
        """
        scored = [
            (self._composite_score(c, cfg.weights), c)
            for c in candidates
        ]
        scored.sort(key=lambda t: t[0], reverse=True)

        if not scored:
            return None

        score, winner = scored[0]
        rationale = self._rationale_precise(winner, fallback_watts, panel_wattage_w, solar_coefficient)
        return self._build_recommendation(
            winner, RecommendationCategory.PRECISE, score, rationale,
        )

    def _select_premium(
        self,
        candidates: List[_ScoredCandidate],
        cfg:        CategoryConfig,
    ) -> Optional[CategorizedRecommendation]:
        """
        Select the Premium winner.

        Primary sort: highest panel count (most capacity / production margin).
        Secondary sort: composite score (efficiency, head/flow margin) to break ties.

        Applies the submersible (stacked impeller) preference rule when
        cfg.prefer_submersible is True:
            If the top-scoring submersible is within
            cfg.submersible_panel_tolerance panels of the overall top-scorer,
            the submersible wins regardless of panel-count ordering.
        """
        if not candidates:
            return None

        scored = [
            (self._composite_score(c, cfg.weights), c)
            for c in candidates
        ]
        # Primary: most panels (highest capacity margin); secondary: composite score
        scored.sort(key=lambda t: (t[1].solar_panels, t[0]), reverse=True)

        # Apply submersible preference if configured
        if cfg.prefer_submersible:
            result = self._apply_submersible_preference(
                scored, cfg.submersible_panel_tolerance,
            )
        else:
            result = scored[0]

        score, winner = result
        rationale = self._rationale_premium(winner, cfg)
        return self._build_recommendation(
            winner, RecommendationCategory.PREMIUM, score, rationale,
        )

    # ── Submersible preference rule ───────────────────────────────────────────

    def _apply_submersible_preference(
        self,
        scored:     List[Tuple[float, _ScoredCandidate]],
        tolerance:  int,
    ) -> Tuple[float, _ScoredCandidate]:
        """
        Return the (score, candidate) for the Premium winner after applying
        the stacked-impeller preference rule.

        Rule: if the best-scoring submersible is within ``tolerance`` panels
        of the overall top-scorer, prefer the submersible.
        """
        best_overall = scored[0]

        # Find best submersible
        submersibles = [
            (s, c) for s, c in scored
            if c.result.pump.pump_type == PumpType.SUBMERSIBLE
        ]
        if not submersibles:
            return best_overall   # no submersibles → use overall winner

        best_subm = submersibles[0]

        # If the overall winner is already a submersible, no adjustment needed
        if best_overall[1].result.pump.pump_type == PumpType.SUBMERSIBLE:
            return best_overall

        # Check panel tolerance
        panel_diff = best_subm[1].solar_panels - best_overall[1].solar_panels
        if panel_diff <= tolerance:
            logger.debug(
                "Premium submersible preference: %s selected over %s "
                "(%d panel diff ≤ tolerance %d)",
                best_subm[1].result.pump.pump_id,
                best_overall[1].result.pump.pump_id,
                panel_diff, tolerance,
            )
            return best_subm

        # Submersible requires too many extra panels — use overall winner
        logger.debug(
            "Premium submersible preference: %s skipped (panel diff %d > tolerance %d); "
            "falling back to %s",
            best_subm[1].result.pump.pump_id,
            panel_diff, tolerance,
            best_overall[1].result.pump.pump_id,
        )
        return best_overall

    # ── Composite scoring ─────────────────────────────────────────────────────

    def _composite_score(
        self,
        candidate: _ScoredCandidate,
        weights:   ScoringWeights,
    ) -> float:
        """
        Compute a weighted composite score (0–100) for a candidate.

        Each dimension is normalised independently to 0–100 before weighting.
        """
        result = candidate.result
        pump   = result.pump
        total_w = weights.total_active_weight()
        if total_w <= 0:
            return 0.0

        dims: float = 0.0

        # ── Panel count score (fewer = better) ────────────────────────────
        if weights.panel_count_weight > 0:
            # Normalise over 1–20 panels (engineering bound)
            panel_score = max(0.0, 100.0 - (candidate.solar_panels - 1) * 5.0)
            dims += panel_score * weights.panel_count_weight

        # ── Efficiency score ──────────────────────────────────────────────
        if weights.efficiency_weight > 0:
            eff_score = min(100.0, max(0.0,
                (pump.efficiency_percent - _EFF_MIN_PCT) /
                max(1e-9, _EFF_MAX_PCT - _EFF_MIN_PCT) * 100.0
            ))
            dims += eff_score * weights.efficiency_weight

        # ── Power match score (operating near BEP) ───────────────────────
        if weights.power_match_weight > 0:
            if pump.rated_power_w > 0 and candidate.op_watts > 0:
                ratio = candidate.op_watts / pump.rated_power_w
                if _BEP_RATIO_LOW <= ratio <= _BEP_RATIO_HIGH:
                    power_score = 100.0
                elif ratio < _BEP_RATIO_LOW:
                    power_score = (ratio / _BEP_RATIO_LOW) * 100.0
                else:
                    power_score = max(0.0, 100.0 - (ratio - _BEP_RATIO_HIGH) * 200.0)
            else:
                power_score = 50.0
            dims += power_score * weights.power_match_weight

        # ── Head margin score (10–30 % is ideal) ─────────────────────────
        if weights.head_margin_weight > 0:
            hm = result.head_margin_percent / 100.0
            if _IDEAL_HM_LOW <= hm <= _IDEAL_HM_HIGH:
                head_score = 100.0
            elif hm < _IDEAL_HM_LOW:
                head_score = 80.0   # works but tight
            elif hm <= 0.50:
                head_score = 100.0 - ((hm - _IDEAL_HM_HIGH) / 0.20) * 30.0
            else:
                head_score = max(0.0, 70.0 - (hm - 0.50) * 100.0)
            dims += head_score * weights.head_margin_weight

        # ── Flow margin score (positive margin, not extreme) ──────────────
        if weights.flow_margin_weight > 0:
            fm = result.flow_margin_percent / 100.0
            if 0.0 <= fm <= 0.50:
                flow_score = 100.0
            elif fm < 0.0:
                flow_score = 0.0
            elif fm <= 1.0:
                flow_score = max(70.0, 100.0 - (fm - 0.50) * 60.0)
            else:
                flow_score = max(0.0, 70.0 - (fm - 1.0) * 70.0)
            dims += flow_score * weights.flow_margin_weight

        # ── Future dimensions (inactive — reliability, production margin) ─
        # When real data is available, implement sub-scorers here and add
        # them to dims with their respective weights.

        return round(dims / total_w, 3)

    # ── Rationale generators ──────────────────────────────────────────────────

    def _rationale_economical(
        self,
        winner: _ScoredCandidate,
        scored: List[Tuple[float, "_ScoredCandidate"]],
    ) -> str:
        pump  = winner.result.pump
        parts = [
            f"Requires {winner.solar_panels} panel(s) — "
            f"{'tied for ' if sum(1 for _, c in scored if c.solar_panels == winner.solar_panels) > 1 else ''}"
            f"fewest in eligible set.",
        ]
        if pump.price_usd is not None:
            parts.append(f"Indicative price USD {pump.price_usd:,.0f}.")
        if not winner.result.curve_based_evaluation:
            parts.append("Panel count based on hydraulic estimate — no performance dataset.")
        return " ".join(parts)

    def _rationale_precise(
        self,
        winner:            _ScoredCandidate,
        fallback_watts:    float,
        panel_wattage_w:   float,
        solar_coefficient: float,
    ) -> str:
        pump   = winner.result.pump
        op_w   = winner.op_watts
        array_output = winner.solar_panels * panel_wattage_w / solar_coefficient
        util_pct = min(999.0, op_w / max(1.0, array_output) * 100.0)
        parts = [
            f"Operating at {op_w:.0f} W — array utilisation ~{util_pct:.0f}%.",
        ]
        hm = winner.result.head_margin_percent
        if _IDEAL_HM_LOW * 100 <= hm <= _IDEAL_HM_HIGH * 100:
            parts.append(f"Head margin {hm:.1f}% is within the ideal 10–30% range.")
        else:
            parts.append(f"Head margin {hm:.1f}%.")
        if not winner.result.curve_based_evaluation:
            parts.append("Power based on hydraulic estimate — no performance dataset.")
        return " ".join(parts)

    def _rationale_premium(
        self,
        winner: _ScoredCandidate,
        cfg:    CategoryConfig,
    ) -> str:
        pump  = winner.result.pump
        parts = [f"Efficiency {pump.efficiency_percent:.0f}% BEP."]
        hm = winner.result.head_margin_percent
        parts.append(f"Head margin {hm:.1f}%.")
        if pump.pump_type == PumpType.SUBMERSIBLE and cfg.prefer_submersible:
            parts.append(
                "Stacked impeller (submersible) preferred for reliability "
                f"within {cfg.submersible_panel_tolerance}-panel tolerance."
            )
        if not winner.result.curve_based_evaluation:
            parts.append("⚠ Envelope-based estimate — add performance dataset for full confidence.")
        return " ".join(parts)

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate(
        economical: Optional[CategorizedRecommendation],
        precise:    Optional[CategorizedRecommendation],
        premium:    Optional[CategorizedRecommendation],
    ) -> RankingValidationResult:
        empty:    List[str] = []
        warnings: List[str] = []

        mapping = {
            RecommendationCategory.ECONOMICAL: economical,
            RecommendationCategory.PRECISE:    precise,
            RecommendationCategory.PREMIUM:    premium,
        }
        for cat, winner in mapping.items():
            if winner is None:
                empty.append(cat.value)
                warnings.append(
                    f"No winner could be selected for the '{cat.value}' category. "
                    "Verify that at least one eligible pump is in the catalog."
                )

        # Warn when categories share the same pump (can happen with small catalogs)
        winners = [w for w in (economical, precise, premium) if w is not None]
        ids = [w.pump.pump_id for w in winners]
        if len(ids) != len(set(ids)):
            warnings.append(
                "Multiple categories selected the same pump. "
                "This is expected when the eligible set is small. "
                "Expand the pump catalog or adjust ranking weights for more diversity."
            )

        return RankingValidationResult(
            categories_evaluated=3,
            categories_with_winner=3 - len(empty),
            empty_categories=empty,
            warnings=warnings,
        )

    # ── Builder ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_recommendation(
        candidate: _ScoredCandidate,
        category:  RecommendationCategory,
        score:     float,
        rationale: str,
    ) -> CategorizedRecommendation:
        result = candidate.result
        return CategorizedRecommendation(
            category=category,
            category_score=round(score, 2),
            selection_rationale=rationale,
            pump=result.pump,
            meets_head_requirement=result.meets_head_requirement,
            meets_flow_requirement=result.meets_flow_requirement,
            head_margin_percent=result.head_margin_percent,
            flow_margin_percent=result.flow_margin_percent,
            operating_wattage_w=candidate.op_watts,
            achievable_gpm=candidate.achievable_gpm if candidate.achievable_gpm is not None else result.achievable_gpm,
            curve_based_evaluation=result.curve_based_evaluation,
            solar_panels=candidate.solar_panels,
            solar_governing_path=candidate.solar_governing_path,
            evaluation_warnings=result.evaluation_warnings,
        )

    # ── Empty result ──────────────────────────────────────────────────────────

    @staticmethod
    def _empty_result(total: int, eligible: int) -> RankedRecommendationSet:
        validation = RankingValidationResult(
            categories_evaluated=3,
            categories_with_winner=0,
            empty_categories=["economical", "precise", "premium"],
            warnings=[
                "No eligible pumps found. "
                "No pump in the catalog meets both the required TDH and flow. "
                "Check requirements or expand the pump catalog."
            ],
        )
        return RankedRecommendationSet(
            economical=None,
            precise=None,
            premium=None,
            total_evaluated=total,
            eligible_count=eligible,
            categories_filled=0,
            validation=validation,
        )

    # ── Future: preference filters (stub) ─────────────────────────────────────

    @staticmethod
    def _apply_preference_filters(
        candidates:             List[_ScoredCandidate],
        voltage_class_pref:     Optional[str],
        pump_type_pref:         Optional[str],
    ) -> List[_ScoredCandidate]:
        """
        [Stub] Apply AC/DC voltage class and pump type preference filters.

        When real business rules and/or client preferences are defined, implement
        this method to narrow the candidate pool before scoring.  The method
        should return the full candidate list if filters produce an empty set
        (fallback to unfiltered).

        Args:
            candidates:         Pre-filtered eligible candidates.
            voltage_class_pref: Preferred VoltageClass value string, or None.
            pump_type_pref:     Preferred PumpType value string, or None.

        Returns:
            Filtered candidate list (or original if no preference / no match).
        """
        filtered = candidates

        if voltage_class_pref:
            preferred = [
                c for c in filtered
                if c.result.pump.voltage_class.value == voltage_class_pref
            ]
            if preferred:
                filtered = preferred
            else:
                logger.debug(
                    "_apply_preference_filters: no candidates match voltage_class=%s; "
                    "preference ignored",
                    voltage_class_pref,
                )

        if pump_type_pref:
            preferred = [
                c for c in filtered
                if c.result.pump.pump_type.value == pump_type_pref
            ]
            if preferred:
                filtered = preferred
            else:
                logger.debug(
                    "_apply_preference_filters: no candidates match pump_type=%s; "
                    "preference ignored",
                    pump_type_pref,
                )

        return filtered
