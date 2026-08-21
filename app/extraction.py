"""LLM extraction layer.

Sends the product image (optional) and SKU to a vision-capable Claude
model and asks for JSON conforming to ExtractedListing. The response is
validated with Pydantic; malformed output raises ExtractionError rather
than propagating unvalidated data.

The Anthropic client is created lazily and injected into the FastAPI app
state so tests can substitute a fake.
"""

import base64
import json
import logging
import os

import anthropic

from app.schemas import ExtractedListing

logger = logging.getLogger(__name__)

MODEL = os.environ.get("RESTOCK_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = 1500

SYSTEM_PROMPT = """You are the intake engine for a B2B surplus building-materials marketplace.
Given a SKU (and a product photo when provided), produce a structured listing draft.

Rules:
- Respond with ONLY a JSON object. No markdown fences, no prose.
- Use this exact schema:
{
  "title": str,                    // short listing title, e.g. "36-in Prehung Interior Door, Primed"
  "category": str,                 // one of: lumber, drywall, roofing, flooring, doors_windows, plumbing, electrical, hvac, structural, fasteners_hardware, paint_finish, other
  "brand": str | null,
  "model_number": str | null,
  "specs": {str: str},             // dimensions, ratings, material, color — only what you can support
  "condition_tier": str,           // one of: new_surplus, like_new, used_serviceable, damaged
  "condition_notes": str,          // 1-2 sentences on observed condition
  "quantity_estimate": str | null, // only if visible in the photo
  "confidence": float              // 0-1, your honest confidence in this extraction
}
- If no photo is provided, infer what you can from the SKU/notes, set condition_tier
  to "new_surplus" only if the notes support it, otherwise your best supported guess,
  and lower confidence accordingly.
- Never invent specs you cannot support from the inputs. Fewer correct specs beat
  many guessed ones."""


class ExtractionError(Exception):
    """Raised when the model returns unusable output."""


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env or export it.")
    return anthropic.Anthropic(api_key=api_key)


def _build_user_content(
    sku: str,
    notes: str | None,
    image_bytes: bytes | None,
    image_media_type: str | None,
) -> list[dict]:
    content: list[dict] = []
    if image_bytes is not None:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_media_type or "image/jpeg",
                    "data": base64.b64encode(image_bytes).decode(),
                },
            }
        )
    text = f"SKU: {sku}"
    if notes:
        text += f"\nSeller notes: {notes}"
    content.append({"type": "text", "text": text})
    return content


def extract_listing(
    client: anthropic.Anthropic,
    sku: str,
    notes: str | None = None,
    image_bytes: bytes | None = None,
    image_media_type: str | None = None,
) -> tuple[ExtractedListing, str]:
    """Run one extraction. Returns (listing, model_name)."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _build_user_content(sku, notes, image_bytes, image_media_type),
            }
        ],
    )

    raw = "".join(block.text for block in response.content if block.type == "text").strip()

    # Defensive: strip accidental code fences before parsing.
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.removeprefix("json").strip()

    try:
        data = json.loads(raw)
        listing = ExtractedListing.model_validate(data)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Model returned unusable output for SKU %s: %s", sku, raw[:300])
        raise ExtractionError(f"Model output failed validation: {exc}") from exc

    return listing, MODEL
