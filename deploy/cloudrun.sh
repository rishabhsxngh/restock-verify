#!/usr/bin/env bash
# Deploy ReStock Verify to Google Cloud Run.
#
# One-time setup (run once per project):
#   gcloud auth login
#   gcloud config set project YOUR_PROJECT_ID
#   gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com
#   echo -n "sk-ant-..." | gcloud secrets create anthropic-api-key --data-file=-
#
# Then deploy (from repo root):
#   ./deploy/cloudrun.sh
set -euo pipefail

SERVICE="${SERVICE:-restock-verify}"
REGION="${REGION:-us-central1}"
PROJECT="$(gcloud config get-value project 2>/dev/null)"

if [[ -z "$PROJECT" ]]; then
  echo "No gcloud project set. Run: gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi

echo "Deploying $SERVICE to $REGION in project $PROJECT..."

gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --timeout 60 \
  --set-secrets "ANTHROPIC_API_KEY=anthropic-api-key:latest"

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')"
echo
echo "Deployed: $URL"
echo "Health:   curl $URL/healthz"
echo "Docs:     $URL/docs"
