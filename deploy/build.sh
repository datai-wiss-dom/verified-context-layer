#!/usr/bin/env bash
# Build the wrapper image and push it to Artifact Registry. The AR repo must already exist
# (deploy TF phase A). The image path here MUST match local.image in the deploy Terraform.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
set -a; source "$REPO_ROOT/.env"; set +a

: "${VCL_PROJECT:?}"; : "${VCL_LOCATION:?}"
REPO_ID="${VCL_AR_REPO:-vcl}"
SERVICE="${VCL_SERVICE_NAME:-vcl-wrapper}"
TAG="${VCL_IMAGE_TAG:-latest}"
IMAGE="${VCL_LOCATION}-docker.pkg.dev/${VCL_PROJECT}/${REPO_ID}/${SERVICE}:${TAG}"

echo ">> building + pushing ${IMAGE}"
gcloud builds submit "$REPO_ROOT" --project "$VCL_PROJECT" \
  --config "$REPO_ROOT/deploy/cloudbuild.yaml" \
  --substitutions="_IMAGE=${IMAGE}"
echo ">> pushed ${IMAGE}"
