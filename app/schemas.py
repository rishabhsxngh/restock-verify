"""Pydantic models for ReStock Verify.

These models define the contract between the LLM extraction layer and the
API response. The LLM is asked to return JSON matching ExtractedListing;
anything that fails validation is rejected rather than passed to the client.
"""

from enum import Enum

from pydantic import BaseModel, Field


class MaterialCategory(str, Enum):
    LUMBER = "lumber"
    DRYWALL = "drywall"
    ROOFING = "roofing"
    FLOORING = "flooring"
    DOORS_WINDOWS = "doors_windows"
    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    HVAC = "hvac"
    STRUCTURAL = "structural"
    FASTENERS_HARDWARE = "fasteners_hardware"
    PAINT_FINISH = "paint_finish"
    OTHER = "other"


class ConditionTier(str, Enum):
    NEW_SURPLUS = "new_surplus"  # unopened / unused overstock
    LIKE_NEW = "like_new"  # opened or shelf-worn, never installed
    USED_SERVICEABLE = "used_serviceable"  # previously installed, functional
    DAMAGED = "damaged"  # visible defects, sold as-is


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExtractedListing(BaseModel):
    """What the LLM extraction layer must return."""

    title: str = Field(..., description="Short human-readable listing title")
    category: MaterialCategory
    brand: str | None = None
    model_number: str | None = None
    specs: dict[str, str] = Field(
        default_factory=dict,
        description="Key/value spec sheet, e.g. {'width': '36 in'}",
    )
    condition_tier: ConditionTier
    condition_notes: str = Field(
        ..., description="One or two sentences describing observed condition"
    )
    quantity_estimate: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)


class VerificationPlan(BaseModel):
    """Deterministic output of the risk engine — not LLM-generated."""

    risk_tier: RiskTier
    required_steps: list[str]
    warranty_attestation_required: bool
    physical_inspection_required: bool


class ListingDraft(BaseModel):
    """Full API response."""

    sku: str
    listing: ExtractedListing
    verification: VerificationPlan
    model_used: str


class HealthResponse(BaseModel):
    status: str
    version: str
