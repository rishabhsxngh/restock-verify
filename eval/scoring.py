"""Field-level scoring for eval cases (pure functions, no API calls).

Spec matching is tolerant of formatting: whitespace, case, and punctuation
are ignored, so a labeled "200 A" matches a model "200A" or "200-amp".
Key matching is tried first; if the model used a different key name
(e.g. "amp_rating" vs "amperage"), the value is searched across all specs.
"""

import re


def norm(value) -> str:
    return str(value).strip().lower()


def squash(value) -> str:
    """Lowercase and drop everything except letters, digits and '/'."""
    return re.sub(r"[^a-z0-9/]", "", str(value).lower())


def spec_hit(expected_key: str, expected_val: str, got: dict[str, str]) -> bool:
    ev = squash(expected_val)
    ek = squash(expected_key)
    squashed = {squash(k): squash(v) for k, v in got.items()}
    if ek in squashed and ev in squashed[ek]:
        return True
    return any(ev in v for v in squashed.values())


def score_case(case: dict, listing) -> dict:
    expected = case["expected"]
    result = {"name": case["name"]}

    result["category_ok"] = norm(listing.category.value) == norm(expected["category"])
    result["condition_ok"] = norm(listing.condition_tier.value) == norm(expected["condition_tier"])

    if expected.get("brand"):
        result["brand_ok"] = listing.brand is not None and norm(expected["brand"]) in norm(
            listing.brand
        )
    if expected.get("model_number"):
        result["model_ok"] = listing.model_number is not None and squash(
            expected["model_number"]
        ) == squash(listing.model_number)

    labeled_specs = expected.get("specs", {})
    if labeled_specs:
        hits = sum(1 for k, v in labeled_specs.items() if spec_hit(k, v, listing.specs))
        result["spec_recall"] = round(hits / len(labeled_specs), 2)
        result["spec_misses"] = [k for k, v in labeled_specs.items() if not spec_hit(k, v, listing.specs)]

    return result


def summarize(results: list[dict]) -> dict:
    summary = {}
    for field in ["category_ok", "condition_ok", "brand_ok", "model_ok"]:
        vals = [r[field] for r in results if field in r]
        if vals:
            summary[field] = f"{sum(vals)}/{len(vals)}"
    recalls = [r["spec_recall"] for r in results if "spec_recall" in r]
    if recalls:
        summary["mean_spec_recall"] = round(sum(recalls) / len(recalls), 2)
    return summary
