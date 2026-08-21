from app.risk import build_verification_plan
from app.schemas import ConditionTier, ExtractedListing, MaterialCategory, RiskTier


def make_listing(**overrides) -> ExtractedListing:
    base = {
        "title": "Test Item",
        "category": MaterialCategory.PAINT_FINISH,
        "specs": {},
        "condition_tier": ConditionTier.NEW_SURPLUS,
        "condition_notes": "Unopened.",
        "confidence": 0.95,
    }
    base.update(overrides)
    return ExtractedListing(**base)


def test_cosmetic_new_surplus_is_low_risk():
    plan = build_verification_plan(make_listing())
    assert plan.risk_tier == RiskTier.LOW
    assert not plan.physical_inspection_required
    assert not plan.warranty_attestation_required


def test_electrical_is_high_risk():
    plan = build_verification_plan(make_listing(category=MaterialCategory.ELECTRICAL))
    assert plan.risk_tier == RiskTier.HIGH
    assert plan.physical_inspection_required
    assert any("inspection" in s.lower() for s in plan.required_steps)


def test_used_condition_bumps_tier():
    plan = build_verification_plan(
        make_listing(
            category=MaterialCategory.LUMBER,  # medium base
            condition_tier=ConditionTier.USED_SERVICEABLE,
        )
    )
    assert plan.risk_tier == RiskTier.HIGH


def test_damaged_cosmetic_becomes_medium():
    plan = build_verification_plan(make_listing(condition_tier=ConditionTier.DAMAGED))
    assert plan.risk_tier == RiskTier.MEDIUM
    assert plan.warranty_attestation_required


def test_high_risk_cannot_exceed_high():
    plan = build_verification_plan(
        make_listing(
            category=MaterialCategory.STRUCTURAL,
            condition_tier=ConditionTier.DAMAGED,
        )
    )
    assert plan.risk_tier == RiskTier.HIGH


def test_low_confidence_forces_manual_review():
    plan = build_verification_plan(make_listing(confidence=0.4))
    assert any("manual review" in s.lower() for s in plan.required_steps)
