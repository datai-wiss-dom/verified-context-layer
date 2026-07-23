#!/usr/bin/env bash
#
# infra/04_verify.sh
# READ-ONLY verifier for the drift-alerting stack (P1–P4). Creates and modifies NOTHING.
#
# Round-trip checks; on the FIRST failure it prints actual vs expected and exits non-zero:
#   1. required APIs enabled (monitoring, logging, secretmanager)
#   2. both secrets exist; the bot token begins 'xoxb-'
#   3. both channels exist, enabled, correct type
#   4. alert policy exists, enabled, attached to EXACTLY the two expected channels,
#      notification rate limit set
#   5. logName projects/<project>/logs/vcl-drift has >=1 VCL_DRIFT_DETECTED entry in 7d
#
# Shared infra/ contract: set -euo pipefail; PROJECT_ID/PROJECT_NUM derived at top
# (no hardcoded ids). This script only reads.
#
set -euo pipefail

PROJECT_ID="${VCL_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: no project set. Export VCL_PROJECT or run: gcloud config set project <id>" >&2
  exit 2
fi
PROJECT_NUM="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
CH_ENV="$(dirname "$0")/channels.env"
POLICY_DISPLAY="VCL Drift Detected"

echo "verifying drift-alerting stack on ${PROJECT_ID} (${PROJECT_NUM})"

fail() { echo "FAIL [$1]: expected ${2}, actual ${3}" >&2; exit 1; }
pass() { echo "  PASS [$1]: ${2}"; }

# ---- 1. required APIs enabled ----
for api in monitoring.googleapis.com logging.googleapis.com secretmanager.googleapis.com; do
  got="$(gcloud services list --enabled --project="${PROJECT_ID}" \
          --filter="config.name=${api}" --format='value(config.name)' 2>/dev/null || true)"
  [[ "${got}" == "${api}" ]] || fail "api:${api}" "enabled" "${got:-NOT_ENABLED}"
  pass "api:${api}" "enabled"
done

# ---- 2. both secrets exist; bot token begins xoxb- ----
for s in vcl-slack-bot-token vcl-slack-signing-secret; do
  gcloud secrets describe "${s}" --project="${PROJECT_ID}" >/dev/null 2>&1 \
    || fail "secret:${s}" "exists" "MISSING"
  pass "secret:${s}" "exists"
done
set +e
tok="$(gcloud secrets versions access latest --secret=vcl-slack-bot-token --project="${PROJECT_ID}" 2>/dev/null)"
trc=$?
set -e
[[ ${trc} -eq 0 && -n "${tok}" ]] || fail "bot-token access" "readable (a version exists)" "rc=${trc}"
prefix="${tok:0:5}"; unset tok   # never keep or print the full token
[[ "${prefix}" == "xoxb-" ]] || fail "bot-token prefix" "xoxb-" "${prefix}"
pass "bot-token prefix" "xoxb-"

# ---- 3. both channels exist, enabled, correct type ----
[[ -f "${CH_ENV}" ]] || fail "channels.env" "present (run 02 first)" "MISSING"
SLACK_ID="$(grep -E '^VCL_SLACK_CHANNEL_ID=' "${CH_ENV}" | cut -d= -f2-)"
EMAIL_ID="$(grep -E '^VCL_EMAIL_CHANNEL_ID=' "${CH_ENV}" | cut -d= -f2-)"
[[ -n "${SLACK_ID}" && -n "${EMAIL_ID}" ]] \
  || fail "channels.env ids" "both present" "slack='${SLACK_ID}' email='${EMAIL_ID}'"

check_channel() {  # $1=id  $2=expected_type
  local id="$1" want="$2" t e
  t="$(gcloud beta monitoring channels describe "${id}" --project="${PROJECT_ID}" --format='value(type)' 2>/dev/null || true)"
  e="$(gcloud beta monitoring channels describe "${id}" --project="${PROJECT_ID}" --format='value(enabled)' 2>/dev/null || true)"
  [[ "${t}" == "${want}" ]] || fail "channel type ${id}" "${want}" "${t:-MISSING}"
  [[ "${e,,}" == "true" ]]  || fail "channel enabled ${id}" "true" "${e:-MISSING}"
  pass "channel ${id}" "type=${want} enabled=true"
}
check_channel "${SLACK_ID}" slack
check_channel "${EMAIL_ID}" email

# ---- 4. policy exists, enabled, EXACTLY the two channels, rate limit set ----
pname="$(gcloud alpha monitoring policies list --project="${PROJECT_ID}" \
          --filter="displayName='${POLICY_DISPLAY}'" --format='value(name)' 2>/dev/null | head -n1 || true)"
[[ -n "${pname}" ]] || fail "policy:${POLICY_DISPLAY}" "exists" "MISSING"
pen="$(gcloud alpha monitoring policies describe "${pname}" --project="${PROJECT_ID}" --format='value(enabled)' 2>/dev/null || true)"
[[ "${pen,,}" == "true" ]] || fail "policy enabled" "true" "${pen:-MISSING}"
period="$(gcloud alpha monitoring policies describe "${pname}" --project="${PROJECT_ID}" \
           --format='value(alertStrategy.notificationRateLimit.period)' 2>/dev/null || true)"
[[ -n "${period}" ]] || fail "policy rate limit" "set (non-empty)" "EMPTY"
mapfile -t attached < <(gcloud alpha monitoring policies describe "${pname}" --project="${PROJECT_ID}" \
                          --flatten='notificationChannels[]' --format='value(notificationChannels)' 2>/dev/null || true)
cnt="${#attached[@]}"
[[ "${cnt}" -eq 2 ]] || fail "policy channel count" "2 (slack+email only)" "${cnt}: ${attached[*]:-none}"
for c in "${attached[@]}"; do
  [[ "${c}" == "${SLACK_ID}" || "${c}" == "${EMAIL_ID}" ]] \
    || fail "policy channel unexpected" "only slack+email" "${c}"
done
printf '%s\n' "${attached[@]}" | grep -qxF "${SLACK_ID}" || fail "policy slack channel" "${SLACK_ID}" "not attached"
printf '%s\n' "${attached[@]}" | grep -qxF "${EMAIL_ID}" || fail "policy email channel" "${EMAIL_ID}" "not attached"
pass "policy:${POLICY_DISPLAY}" "enabled, rate-limit=${period}, exactly slack+email"

# ---- 5. drift log present in the last 7 days ----
LOG="projects/${PROJECT_ID}/logs/vcl-drift"
hit="$(gcloud logging read "logName=\"${LOG}\" AND jsonPayload.event_type=\"VCL_DRIFT_DETECTED\"" \
        --project="${PROJECT_ID}" --freshness=7d --limit=1 --format='value(timestamp)' 2>/dev/null || true)"
[[ -n "${hit}" ]] || fail "drift log (7d)" ">=1 VCL_DRIFT_DETECTED entry in ${LOG}" "none in last 7d"
pass "drift log (7d)" "found entry at ${hit}"

echo "RESULT: OK — all 5 checks passed."
