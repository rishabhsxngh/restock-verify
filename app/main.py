"""ReStock Verify — AI listing-verification API.

POST /v1/listings/draft : image + SKU -> structured listing draft with a
deterministic verification plan.
"""

import logging

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile

from app import extraction
from app.risk import build_verification_plan
from app.schemas import HealthResponse, ListingDraft

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("restock")

VERSION = "0.1.0"

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB

app = FastAPI(
    title="ReStock Verify",
    version=VERSION,
    description=(
        "AI-powered listing verification for a B2B surplus building-materials "
        "marketplace. An LLM extracts specs from a SKU and photo; a "
        "deterministic risk engine assigns the verification steps required "
        "before sale."
    ),
)


def get_llm_client(request: Request):
    """Dependency: reuse one client per process; tests override this."""
    client = getattr(request.app.state, "llm_client", None)
    if client is None:
        client = extraction.get_client()
        request.app.state.llm_client = client
    return client


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", version=VERSION)


@app.post("/v1/listings/draft", response_model=ListingDraft)
async def draft_listing(
    sku: str = Form(..., min_length=1, max_length=120),
    notes: str | None = Form(None, max_length=2000),
    image: UploadFile | None = File(None),
    client=Depends(get_llm_client),
) -> ListingDraft:
    image_bytes = None
    media_type = None

    if image is not None:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported image type {image.content_type!r}. "
                f"Allowed: {sorted(ALLOWED_IMAGE_TYPES)}",
            )
        image_bytes = await image.read()
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image exceeds 8 MB limit.")
        media_type = image.content_type

    try:
        listing, model_used = extraction.extract_listing(
            client,
            sku=sku.strip(),
            notes=notes,
            image_bytes=image_bytes,
            image_media_type=media_type,
        )
    except extraction.ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    plan = build_verification_plan(listing)
    logger.info(
        "Drafted listing sku=%s category=%s risk=%s confidence=%.2f",
        sku,
        listing.category.value,
        plan.risk_tier.value,
        listing.confidence,
    )
    return ListingDraft(sku=sku.strip(), listing=listing, verification=plan, model_used=model_used)
