"""Evaluation harness for the extraction layer.

Each case in eval/cases/*.json contains the model inputs (sku, notes,
optional image path) and expected labels. The harness runs live
extractions and scores field-level accuracy:

- category:        exact match
- condition_tier:  exact match
- brand/model:     case-insensitive match when labeled
- specs:           recall over labeled key/value pairs (case-insensitive)

Usage:
    ANTHROPIC_API_KEY=... python eval/run_eval.py

Add cases by dropping JSON files into eval/cases/ (see sample files).
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.extraction import extract_listing, get_client

CASES_DIR = pathlib.Path(__file__).parent / "cases"


def norm(value) -> str:
    return str(value).strip().lower()


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
        result["model_ok"] = listing.model_number is not None and norm(
            expected["model_number"]
        ) == norm(listing.model_number)

    labeled_specs = expected.get("specs", {})
    if labeled_specs:
        got = {norm(k): norm(v) for k, v in listing.specs.items()}
        hits = sum(
            1 for k, v in labeled_specs.items() if norm(k) in got and norm(v) in got[norm(k)]
        )
        result["spec_recall"] = round(hits / len(labeled_specs), 2)

    return result


def main() -> None:
    cases = sorted(CASES_DIR.glob("*.json"))
    if not cases:
        print("No eval cases found in eval/cases/")
        return

    client = get_client()
    results = []
    for path in cases:
        case = json.loads(path.read_text())
        image_bytes = None
        media_type = None
        if case.get("image"):
            img_path = CASES_DIR / case["image"]
            image_bytes = img_path.read_bytes()
            media_type = case.get("image_media_type", "image/jpeg")

        listing, _ = extract_listing(
            client,
            sku=case["sku"],
            notes=case.get("notes"),
            image_bytes=image_bytes,
            image_media_type=media_type,
        )
        results.append(score_case(case, listing))

    print(json.dumps(results, indent=2))

    bool_fields = ["category_ok", "condition_ok", "brand_ok", "model_ok"]
    for field in bool_fields:
        vals = [r[field] for r in results if field in r]
        if vals:
            print(f"{field}: {sum(vals)}/{len(vals)}")
    recalls = [r["spec_recall"] for r in results if "spec_recall" in r]
    if recalls:
        print(f"mean spec recall: {sum(recalls) / len(recalls):.2f}")


if __name__ == "__main__":
    main()
