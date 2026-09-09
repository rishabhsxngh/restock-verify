"""Scorer tests: run offline, no model calls."""

from app.schemas import ExtractedListing
from eval.scoring import score_case, spec_hit, summarize


def make_listing(**overrides) -> ExtractedListing:
    base = {
        "title": "200A Load Center",
        "category": "electrical",
        "brand": "Square D",
        "model_number": "QO140M200PC",
        "specs": {"amp_rating": "200A", "spaces": "40"},
        "condition_tier": "new_surplus",
        "condition_notes": "Sealed.",
        "quantity_estimate": None,
        "confidence": 0.9,
    }
    base.update(overrides)
    return ExtractedListing.model_validate(base)


def test_spec_hit_ignores_spacing_and_case():
    assert spec_hit("amperage", "200 A", {"amperage": "200a"})


def test_spec_hit_falls_back_across_keys():
    assert spec_hit("amperage", "200 A", {"amp_rating": "200A"})


def test_spec_hit_misses_when_absent():
    assert not spec_hit("amperage", "200 A", {"spaces": "40"})


def test_score_case_full_credit_on_formatting_differences():
    case = {
        "name": "panel",
        "expected": {
            "category": "electrical",
            "condition_tier": "new_surplus",
            "brand": "square d",
            "model_number": "qo140m200pc",
            "specs": {"amperage": "200 a", "spaces": "40"},
        },
    }
    r = score_case(case, make_listing())
    assert r["category_ok"] and r["condition_ok"] and r["brand_ok"] and r["model_ok"]
    assert r["spec_recall"] == 1.0
    assert r["spec_misses"] == []


def test_summarize_counts():
    results = [
        {"category_ok": True, "condition_ok": False, "spec_recall": 1.0},
        {"category_ok": True, "condition_ok": True, "spec_recall": 0.5},
    ]
    s = summarize(results)
    assert s["category_ok"] == "2/2"
    assert s["condition_ok"] == "1/2"
    assert s["mean_spec_recall"] == 0.75
