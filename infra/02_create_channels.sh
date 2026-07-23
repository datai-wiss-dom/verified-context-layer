#!/usr/bin/env bash
#
# infra/02_create_channels.sh
# Idempotently create two Cloud Monitoring notification channels, gcloud ONLY:
#   - slack : displayName vcl-drift-alerts-auto, channel_name '#vcl-drift-alerts',
#             auth_token read from Secret Manager (vcl-slack-bot-token)
#   - email : displayName vcl-steward-email-auto (address from env)
# Writes the resulting channel IDs to infra/channels.env (IDs ONLY, never the token).
#
# PURPOSE: establish whether a Slack *bot* token (xoxb-…) is accepted as auth_token.
# The descriptor does not say, so we do NOT assume. If slack creation fails with the
# token, this script prints the VERBATIM gcloud error, exits non-zero, and does NOT
# fall back to any other approach.
#
# Shared infra/ contract:
#   set -euo pipefail; PROJECT_ID/PROJECT_NUM derived at top (no hardcoded ids);
#   idempotent (look up by displayName, create only if absent);
#   every action confirmed by a round-trip READ of resulting state, not exit code;
#   non-zero exit on any verification mismatch, printing actual vs expected.
#
# Does not touch the three pre-existing channels: it only ever creates the two
# '-auto' displayNames and never updates/deletes/disables anything.
#
set -euo pipefail

PROJECT_ID="${VCL_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: no project set. Export VCL_PROJECT or run: gcloud config set project <id>" >&2
  exit 2
fi
PROJECT_NUM="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"

SLACK_DISPLAY="vcl-drift-alerts-auto"
SLACK_CHANNEL_NAME="#vcl-drift-alerts"
SLACK_SECRET="vcl-slack-bot-token"
EMAIL_DISPLAY="vcl-steward-email-auto"
EMAIL_ADDRESS="${VCL_STEWARD_EMAIL:-${VCL_OWNER_EMAIL:-}}"
OUT_ENV="$(dirname "$0")/channels.env"

echo "project: ${PROJECT_ID} (${PROJECT_NUM})"

# READ helper: the channel id (full resource name) for a displayName, or empty.
find_channel() {
  gcloud beta monitoring channels list --project="${PROJECT_ID}" \
    --filter="displayName=\"$1\"" --format="value(name)" 2>/dev/null | head -n1
}

# describe helper: the type of a channel by id, or empty.
channel_type() {
  gcloud beta monitoring channels describe "$1" --project="${PROJECT_ID}" \
    --format="value(type)" 2>/dev/null || true
}

# ------------------------------ EMAIL channel ------------------------------
if [[ -z "${EMAIL_ADDRESS}" ]]; then
  echo "ERROR: no email address. Export VCL_STEWARD_EMAIL or VCL_OWNER_EMAIL." >&2
  exit 2
fi
email_id="$(find_channel "${EMAIL_DISPLAY}")"
if [[ -n "${email_id}" ]]; then
  echo "email channel: already exists -> ${email_id}"
else
  echo "email channel: creating (${EMAIL_DISPLAY})"
  printf '{"type":"email","displayName":"%s","labels":{"email_address":"%s"}}' \
      "${EMAIL_DISPLAY}" "${EMAIL_ADDRESS}" \
    | gcloud beta monitoring channels create --project="${PROJECT_ID}" \
        --channel-content-from-file=/dev/stdin
  email_id="$(find_channel "${EMAIL_DISPLAY}")"
fi
et="$(channel_type "${email_id}")"
if [[ -z "${email_id}" || "${et}" != "email" ]]; then
  echo "MISMATCH email: expected an id with type=email; actual id='${email_id:-NONE}' type='${et:-NONE}'" >&2
  exit 1
fi
echo "email channel verified: ${email_id} (type=${et})"

# ---------------------- SLACK channel (bot-token probe) --------------------
slack_id="$(find_channel "${SLACK_DISPLAY}")"
if [[ -n "${slack_id}" ]]; then
  echo "slack channel: already exists -> ${slack_id} (bot-token acceptance was decided at first creation)"
else
  echo "slack channel: creating (${SLACK_DISPLAY}); auth_token from Secret Manager (${SLACK_SECRET})"
  set +e
  TOKEN="$(gcloud secrets versions access latest --secret="${SLACK_SECRET}" --project="${PROJECT_ID}" 2>/dev/null)"
  sec_rc=$?
  set -e
  if [[ ${sec_rc} -ne 0 || -z "${TOKEN}" ]]; then
    echo "ERROR: could not read a token from ${SLACK_SECRET} (no version yet, or access denied)." >&2
    exit 2
  fi
  # Build the channel JSON with the token and feed it via /dev/stdin: the token is
  # never in argv (no ps leak) and never written to disk.
  set +e
  create_err="$(printf '{"type":"slack","displayName":"%s","labels":{"channel_name":"%s","auth_token":"%s"}}' \
      "${SLACK_DISPLAY}" "${SLACK_CHANNEL_NAME}" "${TOKEN}" \
    | gcloud beta monitoring channels create --project="${PROJECT_ID}" \
        --channel-content-from-file=/dev/stdin 2>&1 1>/dev/null)"
  rc=$?
  set -e
  unset TOKEN
  if [[ ${rc} -ne 0 ]]; then
    echo "SLACK CHANNEL CREATION FAILED with the bot token. Verbatim gcloud error:" >&2
    echo "-----------------------------------------------------------------------" >&2
    echo "${create_err}" >&2
    echo "-----------------------------------------------------------------------" >&2
    echo "STOP: per task, not falling back to any other approach." >&2
    exit 1
  fi
  slack_id="$(find_channel "${SLACK_DISPLAY}")"
fi
st="$(channel_type "${slack_id}")"
if [[ -z "${slack_id}" || "${st}" != "slack" ]]; then
  echo "MISMATCH slack: expected an id with type=slack; actual id='${slack_id:-NONE}' type='${st:-NONE}'" >&2
  exit 1
fi
echo "slack channel verified: ${slack_id} (type=${st})"

# ------------------------- write channels.env (IDs ONLY) -------------------
umask 077
cat > "${OUT_ENV}" <<EOF
# Cloud Monitoring notification channel IDs — created by infra/02_create_channels.sh.
# IDs only; never tokens/secrets. Gitignored (contains the project-number resource path).
VCL_SLACK_CHANNEL_ID=${slack_id}
VCL_EMAIL_CHANNEL_ID=${email_id}
EOF

# round-trip: read channels.env back and confirm it matches the live IDs.
file_slack="$(grep -E '^VCL_SLACK_CHANNEL_ID=' "${OUT_ENV}" | cut -d= -f2-)"
file_email="$(grep -E '^VCL_EMAIL_CHANNEL_ID=' "${OUT_ENV}" | cut -d= -f2-)"
if [[ "${file_slack}" != "${slack_id}" || "${file_email}" != "${email_id}" ]]; then
  echo "MISMATCH channels.env: file(slack='${file_slack}' email='${file_email}') vs live(slack='${slack_id}' email='${email_id}')" >&2
  exit 1
fi
# guard: no token material in any VALUE line (comment lines are ignored so this
# guard cannot false-positive on its own descriptive comments).
if grep -vE '^[[:space:]]*#' "${OUT_ENV}" | grep -qiE 'xoxb-|auth[_-]?token'; then
  echo "SECURITY: channels.env unexpectedly contains a token-like string — aborting." >&2
  exit 1
fi

echo "channels.env written and verified: ${OUT_ENV}"
echo "RESULT: OK — email + slack channels present and verified; IDs recorded (no token)."
