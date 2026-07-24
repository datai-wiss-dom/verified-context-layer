#!/usr/bin/env bash
#
# infra/03_create_policy.sh
# Idempotently create the Cloud Monitoring alert policy "VCL Drift Detected".
#
# It fires on the structured drift log that `vcl.py enforce` emits:
#   logName = projects/<project>/logs/vcl-drift  AND
#   jsonPayload.event_type = "VCL_DRIFT_DETECTED"
# and notifies the slack + email channels recorded in infra/channels.env.
#
# WHY --policy-from-file (not the create flags): per `gcloud alpha monitoring
# policies create --help`, the flag interface builds only a METRIC-THRESHOLD
# condition (--condition-filter/--if/--duration/--trigger-*). It exposes NO flag for
# a log-match condition (conditionMatchedLog) nor for alertStrategy.notificationRate
# Limit — which log-based alert policies REQUIRE. So the full policy is supplied as a
# document via --policy-from-file (/dev/stdin). Nothing is inferred about flags.
#
# Shared infra/ contract:
#   set -euo pipefail; PROJECT_ID/PROJECT_NUM derived at top (no hardcoded ids);
#   idempotent (look up by displayName, create only if absent);
#   every action confirmed by a round-trip READ of resulting state, not exit code;
#   non-zero exit on any verification mismatch, printing actual vs expected.
#
set -euo pipefail

PROJECT_ID="${VCL_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: no project set. Export VCL_PROJECT or run: gcloud config set project <id>" >&2
  exit 2
fi
PROJECT_NUM="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"

POLICY_DISPLAY="VCL Drift Detected"
CH_ENV="$(dirname "$0")/channels.env"
RESERVED_CHANNEL_ID="11547538545087121616"   # vcl-steward-review — MUST NOT be used

echo "project: ${PROJECT_ID} (${PROJECT_NUM})"

# --- read channel IDs from infra/channels.env (produced by 02_create_channels.sh) ---
if [[ ! -f "${CH_ENV}" ]]; then
  echo "ERROR: ${CH_ENV} not found — run infra/02_create_channels.sh first." >&2
  exit 2
fi
SLACK_ID="$(grep -E '^VCL_SLACK_CHANNEL_ID=' "${CH_ENV}" | cut -d= -f2-)"
EMAIL_ID="$(grep -E '^VCL_EMAIL_CHANNEL_ID=' "${CH_ENV}" | cut -d= -f2-)"
if [[ -z "${SLACK_ID}" || -z "${EMAIL_ID}" ]]; then
  echo "ERROR: could not read both channel IDs from ${CH_ENV}." >&2
  exit 2
fi

# --- guard: the reserved Slack-app channel must never be wired in ---
for cid in "${SLACK_ID}" "${EMAIL_ID}"; do
  if [[ "${cid}" == *"${RESERVED_CHANNEL_ID}"* ]]; then
    echo "ERROR: reserved channel ${RESERVED_CHANNEL_ID} (vcl-steward-review) must not be used." >&2
    exit 2
  fi
done
echo "channels: slack=${SLACK_ID} email=${EMAIL_ID}"

# --- alert documentation: SEE url + the FAIL-SAFE deep link, built from env so a fresh
# provision reproduces the routing (no hardcoded ids/urls). The deep link targets
# steward/walkthrough_substantive.md — the walkthrough with NO re-certify command — so EVERY
# alert lands on the safe default; the cosmetic re-cert is reached only via an onward link
# there, after the steward reads the classification. ---
LOC="${VCL_LOCATION:-us-central1}"
DP_ID="${VCL_DP_ID:-ecommerce-customer-intelligence}"
GIT_REPO="${VCL_GIT_REPO:?set VCL_GIT_REPO (the public repo) so the alert deep link resolves}"
SEE_URL="https://console.cloud.google.com/dataplex/govern/data-products/projects/${PROJECT_ID}/locations/${LOC}/dataProducts/${DP_ID}?project=${PROJECT_ID}"
DEEP_SUB="https://ssh.cloud.google.com/cloudshell/open?cloudshell_git_repo=${GIT_REPO}&cloudshell_tutorial=steward/walkthrough_substantive.md"
POLICY_DOC="$(cat <<EOF
**A Verified Context Layer data product has drifted** — its governed context is being withheld from agents until a steward re-certifies it.

**1. SEE the drifted entry** (Knowledge Catalog; open its *Governance Drift* aspect to read which dimension drifted and the AI cosmetic/substantive assessment):
${SEE_URL}

**2. REVIEW — open the walkthrough** (Cloud Shell). It opens on the safe default: a review guide with NO re-certify command. Read the assessment on the entry, then it routes you — substantive: investigate; cosmetic: an onward link to the re-certify step:
${DEEP_SUB}
EOF
)"

# --- idempotency: look up by displayName ---
find_policy() {
  gcloud alpha monitoring policies list --project="${PROJECT_ID}" \
    --filter="displayName='${POLICY_DISPLAY}'" --format="value(name)" 2>/dev/null | head -n1
}

policy_name="$(find_policy)"
if [[ -n "${policy_name}" ]]; then
  echo "policy: already exists -> ${policy_name}"
else
  echo "policy: creating '${POLICY_DISPLAY}'"
  # Notification rate limit — REQUIRED for a log-match (conditionMatchedLog) policy,
  # and set EXPLICITLY here. period = 3600s (1 hour).
  # Reasoning: a drifted anchor stays drifted until a steward re-seals it, and
  # `vcl.py enforce` re-emits a VCL_DRIFT_DETECTED WARNING on EVERY run. With no rate
  # limit, a persistent drift would notify slack+email on every enforce run / every
  # matching log line — alert fatigue. 1h yields a prompt first alert, then at most
  # one reminder per hour while the DP stays unverified (a useful "still broken" nag),
  # and it resets naturally once the DP is re-sealed. Tunable; 1h balances timeliness
  # against flooding the channel.
  POLICY_JSON="$(cat <<EOF
{
  "displayName": "${POLICY_DISPLAY}",
  "combiner": "OR",
  "conditions": [
    {
      "displayName": "vcl-drift WARNING log entry",
      "conditionMatchedLog": {
        "filter": "logName=\"projects/${PROJECT_ID}/logs/vcl-drift\" AND jsonPayload.event_type=\"VCL_DRIFT_DETECTED\""
      }
    }
  ],
  "alertStrategy": {
    "notificationRateLimit": { "period": "3600s" }
  },
  "notificationChannels": [
    "${SLACK_ID}",
    "${EMAIL_ID}"
  ]
}
EOF
)"
  set +e
  create_out="$(printf '%s' "${POLICY_JSON}" \
    | gcloud alpha monitoring policies create --project="${PROJECT_ID}" \
        --policy-from-file=/dev/stdin 2>&1)"
  rc=$?
  set -e
  if [[ ${rc} -ne 0 ]]; then
    echo "POLICY CREATION FAILED. Verbatim gcloud error:" >&2
    echo "-----------------------------------------------------------------------" >&2
    echo "${create_out}" >&2
    echo "-----------------------------------------------------------------------" >&2
    exit 1
  fi
  policy_name="$(find_policy)"
fi

# --- ensure documentation (runs whether created or found): the fail-safe deep link now
# lives in code, not only in the live resource. Idempotent — update only if it differs. ---
cur_doc="$(gcloud alpha monitoring policies describe "${policy_name}" --project="${PROJECT_ID}" \
  --format="value(documentation.content)" 2>/dev/null || true)"
if [[ "${cur_doc}" != "${POLICY_DOC}" ]]; then
  echo "policy documentation: syncing (SEE url + substantive deep link)"
  printf '%s' "${POLICY_DOC}" | gcloud alpha monitoring policies update "${policy_name}" \
    --project="${PROJECT_ID}" --documentation-from-file=/dev/stdin --documentation-format=text/markdown >/dev/null
else
  echo "policy documentation: already matches (no-op)"
fi

# --- round-trip verification: READ the resulting policy and confirm each field ---
if [[ -z "${policy_name}" ]]; then
  echo "MISMATCH: policy not found after create." >&2
  exit 1
fi
got_period="$(gcloud alpha monitoring policies describe "${policy_name}" --project="${PROJECT_ID}" \
  --format="value(alertStrategy.notificationRateLimit.period)" 2>/dev/null || true)"
got_filter="$(gcloud alpha monitoring policies describe "${policy_name}" --project="${PROJECT_ID}" \
  --format="value(conditions[0].conditionMatchedLog.filter)" 2>/dev/null || true)"
got_channels="$(gcloud alpha monitoring policies describe "${policy_name}" --project="${PROJECT_ID}" \
  --format="value(notificationChannels)" 2>/dev/null || true)"
got_doc="$(gcloud alpha monitoring policies describe "${policy_name}" --project="${PROJECT_ID}" \
  --format="value(documentation.content)" 2>/dev/null || true)"

fail=0
if [[ "${got_period}" != "3600s" ]]; then
  echo "MISMATCH notificationRateLimit.period: expected='3600s' actual='${got_period:-NONE}'" >&2; fail=1
fi
if [[ "${got_filter}" != *"VCL_DRIFT_DETECTED"* || "${got_filter}" != *"/logs/vcl-drift"* ]]; then
  echo "MISMATCH condition filter: expected to contain VCL_DRIFT_DETECTED and /logs/vcl-drift; actual='${got_filter:-NONE}'" >&2; fail=1
fi
if [[ "${got_channels}" != *"${SLACK_ID}"* ]]; then
  echo "MISMATCH: slack channel not attached; actual notificationChannels='${got_channels:-NONE}'" >&2; fail=1
fi
if [[ "${got_channels}" != *"${EMAIL_ID}"* ]]; then
  echo "MISMATCH: email channel not attached; actual notificationChannels='${got_channels:-NONE}'" >&2; fail=1
fi
if [[ "${got_channels}" == *"${RESERVED_CHANNEL_ID}"* ]]; then
  echo "MISMATCH: reserved channel ${RESERVED_CHANNEL_ID} is attached — must not be!" >&2; fail=1
fi
if [[ "${got_doc}" != *"cloudshell_tutorial=steward/walkthrough_substantive.md"* ]]; then
  echo "MISMATCH documentation: expected the deep link to target steward/walkthrough_substantive.md; not found" >&2; fail=1
fi
if [[ "${got_doc}" == *"cloudshell_tutorial=steward/walkthrough_cosmetic.md"* ]]; then
  echo "MISMATCH documentation: must NOT default to walkthrough_cosmetic.md (fail-safe routing)" >&2; fail=1
fi

if [[ "${fail}" -ne 0 ]]; then
  echo "RESULT: FAIL — policy verification mismatch (see above)." >&2
  exit 1
fi
echo "policy verified: ${policy_name}"
echo "RESULT: OK — 'VCL Drift Detected' present; log-match filter, 1h rate limit, slack+email, and documentation deep-links walkthrough_substantive.md (fail-safe)."
