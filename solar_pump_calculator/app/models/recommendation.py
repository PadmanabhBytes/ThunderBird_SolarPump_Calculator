"""
Recommendation domain models.

This module defines:

  RecommendationCategory  — the three client-facing tiers (Economical / Precise / Premium)
  ScoringWeights          — per-dimension weights for a category's scoring formula
  CategoryConfig          — weights + category-specific rules for one tier
  RankingConfig           — full three-tier configuration; holds defaults and
                            a factory method for future config-file loading
  CategorizedRecommendation — the winning pump for a single category (API response)
  RankedRecommendationSet   — wraps all three category winners (API response)
  RankingValidationResult   — result of the post-rank validation step

Architecture notes
------------------
- ScoringWeights / CategoryConfig / RankingConfig are dataclasses, not Pydantic
  models, because they are service-layer configuration objects, not API types.
  They can be serialized to/from JSON via dataclasses.asdict() or loaded from
  a YAML config file in a future iteration.

- CategorizedRecommendation and RankedRecommendationSet are Pydantic models
  because they are serialized in HTTP responses.

- No scores, weights, or reliability values are hard-coded as "real" data.
  RankingConfig.default() defines structurally sound starting weights that
  MUST be replaced with real business-validated values before production use.

Future extension points (stubs, not yet active)
-------------------------------------------------
  ScoringWeights.reliability_score_weight   — weight for manufacturer reliability index
  ScoringWeights.production_margin_weight   — weight for solar production confidence
  CategoryConfig.voltage_class_preference   — preferred VoltageClass (dc/ac/hybrid)
  CategoryConfig.pump_type_preference       — preferred PumpType (submersible/surface/…)
  RankingConfig.load_from_file(path)        — load config from YAML/JSON
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from .pump import Pump, PumpType, VoltageClass

logger = logging.getLogger(__name__)


# ── Category enum ─────────────────────────────────────────────────────────────

class RecommendationCategory(str, Enum):
    """
    The three client-facing recommendation tiers.

    ECONOMICAL — minimum viable system; fewest solar panels, lowest cost.
    PRECISE    — closest production match; balanced, optimized configuration.
    PREMIUM    — highest reliability and production confidence; prefer
                 stacked impeller (submersible) within tolerance of helical option.
    """
    ECONOMICAL = "economical"
    PRECISE    = "precise"
    PREMIUM    = "premium"


# ── Scoring configuration (service-layer dataclasses) ─────────────────────────

@dataclass
class ScoringWeights:
    """
    Per-dimension scoring weights for one recommendation category.

    Each weight is a float in [0.0, 1.0].  The ranking engine normalises
    them so they do not need to sum to 1.0, but should sum to > 0 for any
    meaningful ranking.

    Dimensions
    ----------
    panel_count_weight      : Reward fewer solar panels (primary for Economical).
    power_match_weight      : Reward operating near rated BEP power (primary for Precise).
    head_margin_weight      : Reward ideal head margin (10–30 %).
    flow_margin_weight      : Reward positive flow headroom without extreme oversizing.
    efficiency_weight       : Reward higher BEP efficiency (primary for Premium).

    Future dimensions (inactive — weights default to 0.0)
    ------------------------------------------------------
    reliability_score_weight  : Weight for a manufacturer reliability index.
                                Activate when real reliability data is loaded.
    production_margin_weight  : Weight for solar production confidence factor.
                                Activate when irradiance dataset integration is ready.
    """
    panel_count_weight:         float = 0.0
    power_match_weight:         float = 0.0
    head_margin_weight:         float = 0.0
    flow_margin_weight:         float = 0.0
    efficiency_weight:          float = 0.0
    # Future — set to 0.0 until real data is available
    reliability_score_weight:   float = 0.0
    production_margin_weight:   float = 0.0

    def total_active_weight(self) -> float:
        """Sum of all non-future weights.  Used for normalisation."""
        return (
            self.panel_count_weight
            + self.power_match_weight
            + self.head_margin_weight
            + self.flow_margin_weight
            + self.efficiency_weight
        )


@dataclass
class CategoryConfig:
    """
    Full configuration for one recommendation category.

    Args:
        weights                     : Scoring dimension weights.
        prefer_submersible          : If True, the selection logic will prefer
                                      a submersible (stacked impeller) pump over
                                      a non-submersible when the panel count
                                      difference is within ``submersible_panel_tolerance``.
                                      Used in the Premium category by default.
        submersible_panel_tolerance : Maximum extra panels a submersible may
                                      require vs. the top non-submersible before
                                      the preference is dropped.  Default = 1.
        voltage_class_preference    : [Future] Preferred VoltageClass. When set,
                                      pumps of this class receive a scoring bonus.
                                      None = no preference.
        pump_type_preference        : [Future] Preferred PumpType. None = no preference.
        description                 : Human-readable description of this category's
                                      selection philosophy.
    """
    weights:                     ScoringWeights
    prefer_submersible:          bool             = False
    submersible_panel_tolerance: int              = 1
    voltage_class_preference:    Optional[str]    = None   # VoltageClass.value or None
    pump_type_preference:        Optional[str]    = None   # PumpType.value or None
    description:                 str              = ""


@dataclass
class RankingConfig:
    """
    Full three-tier ranking configuration.

    Holds one :class:`CategoryConfig` per recommendation tier.
    Obtain via :meth:`RankingConfig.default` for sane starting weights, or
    construct manually to apply real business-validated criteria.

    Future: load from a YAML/JSON config file via ``RankingConfig.load_from_file(path)``.
    """
    economical: CategoryConfig
    precise:    CategoryConfig
    premium:    CategoryConfig

    @staticmethod
    def default() -> "RankingConfig":
        """
        Return the default ranking configuration.

        The weights here encode the structural intent of each category.
        They are starting points — replace with real business-validated
        values once production requirements are defined.

        DO NOT treat these as authoritative engineering numbers.
        """
        return RankingConfig(
            economical=CategoryConfig(
                description=(
                    "Minimum viable system. "
                    "Fewest solar panels, lowest cost, budget-oriented."
                ),
                weights=ScoringWeights(
                    panel_count_weight=0.60,   # primary: minimize panels
                    power_match_weight=0.10,   # secondary: reasonable power match
                    head_margin_weight=0.15,   # adequate headroom
                    flow_margin_weight=0.15,   # adequate flow headroom
                    efficiency_weight=0.00,    # not a priority for budget tier
                ),
                prefer_submersible=False,
            ),
            precise=CategoryConfig(
                description=(
                    "Closest production match. "
                    "Balanced, optimized for the specific operating point."
                ),
                weights=ScoringWeights(
                    panel_count_weight=0.15,   # matters but not dominant
                    power_match_weight=0.40,   # primary: operate near BEP
                    head_margin_weight=0.25,   # ideal 10–30% margin
                    flow_margin_weight=0.20,   # adequate but not excessive
                    efficiency_weight=0.00,    # not the primary concern here
                ),
                prefer_submersible=False,
            ),
            premium=CategoryConfig(
                description=(
                    "Highest reliability and production confidence. "
                    "Prefer stacked impeller (submersible) within panel tolerance."
                ),
                weights=ScoringWeights(
                    panel_count_weight=0.05,   # minor concern at premium tier
                    power_match_weight=0.15,   # balanced power match
                    head_margin_weight=0.30,   # strong headroom for reliability
                    flow_margin_weight=0.20,   # comfortable flow headroom
                    efficiency_weight=0.30,    # primary: high BEP efficiency
                ),
                prefer_submersible=True,
                submersible_panel_tolerance=1,
            ),
        )

    @staticmethod
    def load_from_file(path: str) -> "RankingConfig":
        """
        [Stub] Load ranking configuration from a YAML or JSON file.

        Implement this method when real business rules are ready to be
        managed as external configuration rather than code.

        Args:
            path: Filesystem path to the config file.

        Raises:
            NotImplementedError: Always — stub only.
        """
        raise NotImplementedError(
            "RankingConfig.load_from_file is not yet implemented. "
            "Define category weights in a YAML/JSON file and add the "
            "loading logic here."
        )


# ── API response models (Pydantic) ────────────────────────────────────────────

class CategorizedRecommendation(BaseModel):
    """
    The winning pump for a single recommendation category.

    Contains the pump identity, its solar sizing, operating-point data,
    and the rationale explaining why it won this category.
    """
    # ── Category ──────────────────────────────────────────────────────────────
    category: RecommendationCategory = Field(
        ..., description="Which recommendation tier this pump was selected for"
    )
    category_score: float = Field(
        ..., ge=0.0, le=100.0,
        description=(
            "Composite score (0–100) for this category. "
            "Reflects how well the pump matches this tier's weighted criteria. "
            "Not comparable across categories."
        ),
    )
    selection_rationale: str = Field(
        ...,
        description=(
            "Human-readable explanation of why this pump was selected for "
            "this category, referencing the dominant scoring dimensions."
        ),
    )

    # ── Pump identity ─────────────────────────────────────────────────────────
    pump: Pump

    # ── Operating-point metrics ───────────────────────────────────────────────
    meets_head_requirement: bool = Field(
        ..., description="True if the pump can reach the required TDH"
    )
    meets_flow_requirement: bool = Field(
        ..., description="True if the pump can deliver the required GPM at that TDH"
    )
    head_margin_percent: float = Field(
        ..., description="(catalog_max_head − required_TDH) / required_TDH × 100"
    )
    flow_margin_percent: float = Field(
        ..., description="(catalog_max_flow − required_GPM) / required_GPM × 100"
    )

    # ── Curve-based operating data (None when no dataset is available) ────────
    operating_wattage_w: Optional[float] = Field(
        None,
        description=(
            "Minimum power (W) at which this pump delivers the required GPM "
            "at the required TDH. None when no performance dataset exists."
        ),
    )
    achievable_gpm: Optional[float] = Field(
        None,
        description="GPM delivered at operating_wattage_w and required TDH.",
    )
    curve_based_evaluation: bool = Field(
        False,
        description=(
            "True when the operating point was derived from a real performance dataset. "
            "False = catalog envelope estimate — accuracy reduced."
        ),
    )

    # ── Solar sizing for this specific pump ───────────────────────────────────
    solar_panels: int = Field(
        ...,
        description=(
            "Number of solar panels required for this pump at this operating point. "
            "Computed from the pump's actual operating_wattage_w when available, "
            "or from a hydraulic power estimate otherwise."
        ),
    )
    solar_governing_path: Literal["production", "deadhead", "curve_bilinear"] = Field(
        ...,
        description="Sizing path that set the final panel count.",
    )

    # ── Data quality ──────────────────────────────────────────────────────────
    evaluation_warnings: List[str] = Field(
        default_factory=list,
        description=(
            "Non-fatal data-quality issues encountered during evaluation. "
            "Inspect when curve_based_evaluation is False."
        ),
    )


class RankingValidationResult(BaseModel):
    """
    Result of the post-ranking validation step.

    Reports which categories were filled, which are empty, and why.
    Consumers should surface validation_warnings to the end user.
    """
    categories_evaluated:  int = Field(..., description="Always 3")
    categories_with_winner: int = Field(..., description="0–3")
    empty_categories: List[str] = Field(
        default_factory=list,
        description="Category names that produced no winner.",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Explanations for empty categories or degraded results.",
    )


class RankedRecommendationSet(BaseModel):
    """
    The complete three-tier recommendation result for one calculation request.

    Each category slot holds the single best pump for that tier, or None if
    no eligible pump could be identified (e.g., catalog has no pumps that meet
    head and flow requirements).
    """
    # ── Category winners ──────────────────────────────────────────────────────
    economical: Optional[CategorizedRecommendation] = Field(
        None,
        description=(
            "Minimum viable system recommendation. "
            "Fewest panels, budget-oriented."
        ),
    )
    precise: Optional[CategorizedRecommendation] = Field(
        None,
        description=(
            "Balanced recommendation optimized for the operating point. "
            "Closest solar production match."
        ),
    )
    premium: Optional[CategorizedRecommendation] = Field(
        None,
        description=(
            "Highest-reliability recommendation. "
            "Favors stacked impeller (submersible) within panel tolerance."
        ),
    )

    # ── Summary metadata ──────────────────────────────────────────────────────
    total_evaluated:      int = Field(..., description="Total pumps assessed")
    eligible_count:       int = Field(..., description="Pumps meeting head and flow requirements")
    categories_filled:    int = Field(..., description="How many of the 3 tiers have a winner (0–3)")
    validation:           RankingValidationResult

    @property
    def has_any_recommendation(self) -> bool:
        return self.categories_filled > 0

    @property
    def all_categories_filled(self) -> bool:
        return self.categories_filled == 3
