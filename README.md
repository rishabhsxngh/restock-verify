# ReStock Verify

AI-powered listing verification for a B2B surplus building-materials marketplace.

A supplier photographs a lot of surplus stock and submits it with a SKU. A
vision-capable LLM extracts specs and drafts a structured listing; a
deterministic risk engine then decides what verification the platform requires
before the material can be sold — cosmetic overstock sails through, while
electrical or structural material requires physical inspection and a
warranty attestation.

Built as a production implementation of a verification pipeline I designed
for a B2B marketplace concept: liability-sensitive decisions (risk tier,
required steps) are rule-based and auditable, while the LLM is confined to
what it is good at — reading messy real-world inputs into structured data.

## Architecture

```
 photo + SKU + notes
        │
        ▼
 FastAPI  POST /v1/listings/draft
        │
        ▼
 Extraction layer (Claude vision)
   - strict JSON schema, validated with Pydantic
   - malformed output → 502, never passed through
        │
        ▼
 Risk engine (deterministic, tested)
   - category risk (electrical/structural/plumbing/HVAC/roofing = high)
   - condition bump (used/damaged = +1 tier)
   - confidence gate (< 0.70 → manual review)
        │
        ▼
 ListingDraft JSON: listing + verification plan
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # add your Anthropic API key
export $(cat .env | xargs)
uvicorn app.main:app --reload
```

Try it:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/listings/draft \
  -F "sku=Square D QO140M200PC" \
  -F "notes=Factory sealed, cancelled commercial order" \
  -F "image=@panel.jpg" | python -m json.tool
```

Example response (abridged):

```json
{
  "sku": "Square D QO140M200PC",
  "listing": {
    "title": "200A Load Center, 40-Space",
    "category": "electrical",
    "condition_tier": "new_surplus",
    "confidence": 0.9
  },
  "verification": {
    "risk_tier": "high",
    "physical_inspection_required": true,
    "required_steps": [
      "Seller confirms quantity and lot location",
      "Photo record attached to listing at time of intake",
      "Physical inspection by seller rep with sign-off",
      "Code-compliance status documented (regulated categories)",
      "Buyer acceptance recorded at pickup"
    ]
  }
}
```

Interactive docs at `http://127.0.0.1:8000/docs`.

## Tests

```bash
pytest -q        # offline — the LLM client is faked
ruff check .
```

## Evaluation

Labeled cases live in `eval/cases/` (six SKU-only cases across electrical,
plumbing, HVAC, drywall, lumber, and doors). The harness runs live
extractions and scores field-level accuracy:

```bash
python eval/run_eval.py
```

Scoring (`eval/scoring.py`, unit-tested offline):

- `category`, `condition_tier`: exact match
- `brand`: case-insensitive substring; `model_number`: match ignoring punctuation/spacing
- `specs`: recall over labeled key/value pairs, tolerant of formatting
  (`"200 A"` matches `"200A"`) and key naming (`amperage` vs `amp_rating`);
  misses are reported per case so prompt changes can be targeted

## Try it in Postman

Import `postman/ReStock_Verify.postman_collection.json`. It includes the
health check, a SKU-only draft, a photo draft, and the 422/415 error paths,
each with response assertions. Set `base_url` to local or your Cloud Run URL.

## Deploy to Google Cloud Run

One-time setup:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

# Store the API key in Secret Manager (never in the image)
printf '%s' "$ANTHROPIC_API_KEY" | gcloud secrets create anthropic-api-key --data-file=-
```

Then:

```bash
./deploy/cloudrun.sh
```

The script builds from the Dockerfile, injects the secret, scales to zero
when idle, and prints the public HTTPS URL plus `/healthz` and `/docs` links.

## Design notes

- **Why the risk engine isn't the LLM's job.** Verification requirements
  are the platform's liability policy. Rules make identical materials get
  identical treatment, and every decision is explainable to a seller.
- **Why validated JSON.** Downstream systems (listing DB, seller UI)
  should never see unvalidated model output. Pydantic enforces the
  contract; violations fail loudly with a 502.
- **Why a confidence gate.** The model self-reports confidence; below
  0.70 a human reviews regardless of category. Cheap insurance against
  silent garbage.

## Roadmap

- Batch intake endpoint for multi-lot pallets
- Spec enrichment from manufacturer catalog lookups
- Image-based condition scoring evaluated against inspector labels
