"""Deterministic risk-tiering engine.

The LLM describes the material; this module decides how much verification
the platform requires before the listing can go live. Keeping this logic
out of the LLM makes the platform's liability rules auditable and
consistent — two listings of the same category and condition always get
the same verification plan.

Risk model (mirrors the ReStock platform design):
- Category risk: materials whose failure after installation carries
  safety or code implications (electrical, structural, plumbing, HVAC,
  roofing) are inherently higher risk than cosmetic materials.
- Condition risk: previously installed or damaged material raises the
  tier by one step.
- Confidence gate: low extraction confidence forces human review
  regardless of tier.
"""

from app.schemas import (
    ConditionTier,
    ExtractedListing,
    MaterialCategory,
    RiskTier,
    VerificationPlan,
)

HIGH_RISK_CATEGORIES = {
    MaterialCategory.ELECTRICAL,
    MaterialCategory.STRUCTURAL,
    MaterialCategory.PLUMBING,
    MaterialCategory.HVAC,
    MaterialCategory.ROOFING,
}

MEDIUM_RISK_CATEGORIES = {
    MaterialCategory.DOORS_WINDOWS,
    MaterialCategory.FLOORING,
    MaterialCategory.DRYWALL,
    MaterialCategory.LUMBER,
}

CONFIDENCE_REVIEW_THRESHOLD = 0.70

_BASE_STEPS = [
    "Seller confirms quantity and lot location",
    "Photo record attached to listing at time of intake",
]

_MEDIUM_STEPS = [
    "Seller attests to condition tier in writing",
    "Buyer acceptance recorded at pickup",
]

_HIGH_STEPS = [
    "Physical inspection by seller rep with sign-off",
    "Code-compliance status documented (regulated categories)",
    "Buyer acceptance recorded at pickup",
]


def _category_base_tier(category: MaterialCategory) -> RiskTier:
    if category in HIGH_RISK_CATEGORIES:
        return RiskTier.HIGH
    if category in MEDIUM_RISK_CATEGORIES:
        return RiskTier.MEDIUM
    return RiskTier.LOW


def _bump(tier: RiskTier) -> RiskTier:
    order = [RiskTier.LOW, RiskTier.MEDIUM, RiskTier.HIGH]
    return order[min(order.index(tier) + 1, len(order) - 1)]


def build_verification_plan(listing: ExtractedListing) -> VerificationPlan:
    tier = _category_base_tier(listing.category)

    # Previously installed or damaged material is one tier riskier.
    if listing.condition_tier in (
        ConditionTier.USED_SERVICEABLE,
        ConditionTier.DAMAGED,
    ):
        tier = _bump(tier)

    steps = list(_BASE_STEPS)
    if tier == RiskTier.MEDIUM:
        steps += _MEDIUM_STEPS
    elif tier == RiskTier.HIGH:
        steps += _HIGH_STEPS

    # Low-confidence extraction always forces a human check, independent
    # of the material's own risk.
    if listing.confidence < CONFIDENCE_REVIEW_THRESHOLD:
        steps.append("Manual review: extraction confidence below threshold")

    return VerificationPlan(
        risk_tier=tier,
        required_steps=steps,
        warranty_attestation_required=(tier != RiskTier.LOW),
        physical_inspection_required=(tier == RiskTier.HIGH),
    )
