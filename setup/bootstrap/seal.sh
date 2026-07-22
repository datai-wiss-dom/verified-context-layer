#!/usr/bin/env bash
# Step 8 — runtime finish. vcl.py seal writes the verification aspect VALUES (source_tier,
# anchors, certified_text). This is the DYNAMIC state Terraform deliberately does not own.
# All args come from .env; no literals. The DQ scan must have RUN once before this, or the
# quality anchor is skipped (see SETUP.md).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
set -a; source "$REPO_ROOT/.env"; set +a

: "${VCL_PROJECT:?}"; : "${VCL_PROJECT_NUMBER:?}"; : "${VCL_LOCATION:?}"
: "${VCL_DP_RESOURCE:?}"; : "${VCL_ASPECT_TYPE:?}"
DP_ENTRY="${VCL_DP_RESOURCE#*/entries/}"   # the DP entry is the resource minus the entries/ prefix

python3 "$REPO_ROOT/src/vcl.py" seal \
  --project        "$VCL_PROJECT" \
  --project-number "$VCL_PROJECT_NUMBER" \
  --location       "$VCL_LOCATION" \
  --entry-group    "${VCL_ENTRY_GROUP:-@dataplex}" \
  --dp-entry       "$DP_ENTRY" \
  --dp-resource    "$VCL_DP_RESOURCE" \
  --aspect-type    "$VCL_ASPECT_TYPE" \
  --quality-scan   "customers=${VCL_QUALITY_SCAN_ID:-customers-quality}:24"
