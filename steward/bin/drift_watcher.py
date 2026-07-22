#!/usr/bin/env python3
"""Drift alert watcher — the steward-workflow push trigger.

SEPARATE from vcl.py's enforce (PHASE_SPEC STOP trigger: do NOT modify enforce to publish).
It only READS the stored state and publishes an alert:
  1. read the `verification` aspect -> source_tier (the verdict, written by vcl.py).
  2. if source_tier != "verified": read the `governance-drift` DISPLAY aspect for the
     advisory AI classification, choose the matching walkthrough deep link, and publish a
     Pub/Sub message carrying that deep link.
It never writes any verdict, never calls seal/enforce, and never reads into the gate.

Fail-safe: if the classification is missing/unknown, it links the SUBSTANTIVE walkthrough
(which contains no seal command) — a misread degrades to wrong-but-safe, never dangerous.

Trigger (demo): run this on demand or on a schedule (e.g. Cloud Scheduler -> Cloud Run).
It is a poller over the stored verdict, NOT an enforce hook. Config from repo-root .env.
"""
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_REPO, ".env"))
except Exception:  # noqa: BLE001
    pass

PROJECT = os.environ["VCL_PROJECT"]
PROJECT_NUMBER = os.environ["VCL_PROJECT_NUMBER"]
LOCATION = os.environ["VCL_LOCATION"]
DP_ID = os.environ.get("VCL_DP_ID", "ecommerce-customer-intelligence")
ENTRY_GROUP = os.environ.get("VCL_ENTRY_GROUP", "@dataplex")
VERIFICATION_AT = os.environ["VCL_ASPECT_TYPE"]
GIT_REPO = os.environ.get("VCL_GIT_REPO", "https://github.com/your-org/your-repo")
TOPIC = os.environ.get("VCL_ALERT_TOPIC", "vcl-governance-drift-alerts")
DP_RESOURCE = os.environ["VCL_DP_RESOURCE"]

DP_ENTRY = f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/dataProducts/{DP_ID}"
DRIFT_AT = f"projects/{PROJECT}/locations/{LOCATION}/aspectTypes/governance-drift"


def _lookup(aspect_type):
    p = subprocess.run(
        ["gcloud", "dataplex", "entries", "lookup", DP_ENTRY, "--entry-group", ENTRY_GROUP,
         "--location", LOCATION, "--project", PROJECT, "--view", "CUSTOM",
         "--aspect-types", aspect_type, "--format", "json"],
        capture_output=True, text=True, timeout=90)
    if p.returncode != 0:
        return {}
    return json.loads(p.stdout) if p.stdout.strip() else {}


def _aspect_data(entry_json, needle):
    for k, v in entry_json.get("aspects", {}).items():
        if needle in k:
            return v.get("data", {})
    return None


def main():
    verd = _aspect_data(_lookup(VERIFICATION_AT), "verification") or {}
    tier = verd.get("source_tier")
    if tier == "verified":
        print("watcher: source_tier=verified — nothing to alert.")
        return 0

    drift = _aspect_data(_lookup(DRIFT_AT), "governance-drift") or {}
    classification = drift.get("ai_classification")
    # Fail-safe: unknown/missing classification -> substantive walkthrough (no seal command).
    tutorial = ("steward/walkthrough_cosmetic.md" if classification == "cosmetic"
                else "steward/walkthrough_substantive.md")
    deep_link = (f"https://ssh.cloud.google.com/cloudshell/open"
                 f"?cloudshell_git_repo={GIT_REPO}&cloudshell_tutorial={tutorial}")

    message = {
        "event": "governance_drift",
        "dp_resource": DP_RESOURCE,
        "dp_id": DP_ID,
        "source_tier": tier,
        "drifted_dimensions": verd.get("drift_summary", []),
        "ai_classification": classification,
        "drifted_at": drift.get("drifted_at") or verd.get("drift_detected_at"),
        "deep_link": deep_link,
    }
    p = subprocess.run(
        ["gcloud", "pubsub", "topics", "publish", TOPIC, "--project", PROJECT,
         "--message", json.dumps(message)],
        capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        print(f"watcher: publish failed: {p.stderr.strip()[:200]}", file=sys.stderr)
        return 1
    print(f"watcher: published drift alert to {TOPIC} ({p.stdout.strip()})")
    print(json.dumps(message, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
