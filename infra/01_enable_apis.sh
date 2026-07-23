#!/usr/bin/env bash
#
# infra/01_enable_apis.sh
# Enable the Google Cloud APIs the VCL drift-alerting + secrets path needs:
#   monitoring, logging, secretmanager.
# Deliberately does NOT enable cloudscheduler or run — not needed yet.
#
# Shared contract for every script in infra/:
#   - set -euo pipefail
#   - PROJECT_ID / PROJECT_NUM declared once at the top (never hardcoded inline;
#     derived, so this is safe to commit to a public repo)
#   - idempotent: a second run is a no-op
#   - every action is confirmed by a round-trip READ of the resulting state,
#     NOT by the command's exit code
#   - exits non-zero on any verification mismatch, printing actual vs expected
#
set -euo pipefail

# --- config (derived; no hardcoded project ids) -----------------------------
PROJECT_ID="${VCL_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: no project set. Export VCL_PROJECT or run: gcloud config set project <id>" >&2
  exit 2
fi
PROJECT_NUM="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"

REQUIRED_APIS=(
  monitoring.googleapis.com
  logging.googleapis.com
  secretmanager.googleapis.com
)

echo "project: ${PROJECT_ID} (${PROJECT_NUM})"
echo "required APIs: ${REQUIRED_APIS[*]}"

# --- helper: is this API currently enabled? (a READ) ------------------------
api_enabled() {
  gcloud services list --enabled --project="${PROJECT_ID}" \
    --filter="config.name=$1" --format='value(config.name)' 2>/dev/null
}

# --- action: enable only what is not already enabled (2nd run => no-op) ------
for api in "${REQUIRED_APIS[@]}"; do
  if [[ "$(api_enabled "${api}")" == "${api}" ]]; then
    echo "  already enabled : ${api}"
  else
    echo "  enabling        : ${api}"
    gcloud services enable "${api}" --project="${PROJECT_ID}"
  fi
done

# --- verification: round-trip READ each API's resulting state ---------------
# Trust the read-back, not the enable command's exit code.
fail=0
for api in "${REQUIRED_APIS[@]}"; do
  got="$(api_enabled "${api}")"
  if [[ "${got}" == "${api}" ]]; then
    echo "  verified        : ${api} (enabled)"
  else
    echo "  MISMATCH        : ${api} -> expected='${api}' actual='${got:-NOT_ENABLED}'" >&2
    fail=1
  fi
done

if [[ "${fail}" -ne 0 ]]; then
  echo "RESULT: FAIL — one or more required APIs are not enabled (see mismatches above)." >&2
  exit 1
fi
echo "RESULT: OK — all ${#REQUIRED_APIS[@]} required APIs enabled and verified by read-back."
