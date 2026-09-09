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
from eval.scoring import score_case, summarize

CASES_DIR = pathlib.Path(__file__).parent / "cases"


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

    for k, v in summarize(results).items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
