#!/usr/bin/env python3
"""Backend write step for the steward workflow: populate the DISPLAY-ONLY Governance Drift
aspect on a drifted Data Product's entry.

This is NOT a verdict and the wrapper's gate NEVER reads it (ARCHITECTURE INV-5, the
STEWARD_WORKFLOW "two aspects" rule). It mirrors, for the steward's eyes on the entry page,
what already drifted (from the `verification` aspect) plus the advisory triage read.

It READS the verification aspect (drift_summary, drift_detected_at) and takes the advisory
triage fields as args; it WRITES only the `governance-drift` aspect. It never writes the
verification aspect and never calls seal/enforce.

Usage:
  python3 steward/bin/write_drift_aspect.py \
      --classification substantive \
      --reasoning "..." --recommendation "review carefully before re-certifying"
Config (project, dp, etc.) comes from the repo-root .env.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_REPO, ".env"))
except Exception:  # noqa: BLE001
    pass

def _sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


# Config self-derives so this runs BOTH locally (with repo-root .env) and in Cloud Shell
# (no .env in the clone): fall back to GOOGLE_CLOUD_PROJECT / `gcloud config` for the
# project and `gcloud projects describe` for the number; structural defaults for the rest.
PROJECT = (os.environ.get("VCL_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
           or _sh(["gcloud", "config", "get-value", "project"]))
PROJECT_NUMBER = (os.environ.get("VCL_PROJECT_NUMBER")
                  or _sh(["gcloud", "projects", "describe", PROJECT,
                          "--format=value(projectNumber)"]))
LOCATION = os.environ.get("VCL_LOCATION", "us-central1")
DP_ID = os.environ.get("VCL_DP_ID", "ecommerce-customer-intelligence")
ENTRY_GROUP = os.environ.get("VCL_ENTRY_GROUP", "@dataplex")
ASPECT_TYPE = (os.environ.get("VCL_ASPECT_TYPE")
               or f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/aspectTypes/verification")

DP_ENTRY = f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/dataProducts/{DP_ID}"
DRIFT_KEY = f"{PROJECT_NUMBER}.{LOCATION}.governance-drift"
DRIFT_ASPECT_TYPE = f"projects/{PROJECT}/locations/{LOCATION}/aspectTypes/governance-drift"


def _run_json(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:300])
    return json.loads(p.stdout) if p.stdout.strip() else {}


def read_verification():
    """Read source_tier + drift_summary + drift_detected_at from the verification aspect."""
    out = _run_json([
        "gcloud", "dataplex", "entries", "lookup", DP_ENTRY,
        "--entry-group", ENTRY_GROUP, "--location", LOCATION, "--project", PROJECT,
        "--view", "CUSTOM", "--aspect-types", ASPECT_TYPE, "--format", "json",
    ])
    for k, v in out.get("aspects", {}).items():
        if "verification" in k:
            d = v.get("data", {})
            return d.get("source_tier"), d.get("drift_summary", []), d.get("drift_detected_at")
    return None, [], None


def write_governance_drift(drifted_dims, drifted_at, classification, reasoning, recommendation):
    data = {
        "status": "PENDING_REVIEW",
        "drifted_dimensions": drifted_dims,
        "ai_classification": classification,
        "ai_reasoning": reasoning,
        "ai_recommendation": recommendation,
        "drifted_at": drifted_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    payload = {DRIFT_KEY: {"data": data}}
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(payload, f)
    try:
        _run_json([
            "gcloud", "dataplex", "entries", "update-aspects", DP_ENTRY,
            "--entry-group", ENTRY_GROUP, "--location", LOCATION, "--project", PROJECT,
            "--aspects", path,
        ])
    finally:
        os.unlink(path)
    return data


def read_governance_drift():
    out = _run_json([
        "gcloud", "dataplex", "entries", "lookup", DP_ENTRY, "--entry-group", ENTRY_GROUP,
        "--location", LOCATION, "--project", PROJECT, "--view", "CUSTOM",
        "--aspect-types", DRIFT_ASPECT_TYPE, "--format", "json",
    ])
    for k, v in out.get("aspects", {}).items():
        if "governance-drift" in k:
            return v.get("data", {})
    return None


def resolve_governance_drift():
    """Flip the display aspect's status PENDING_REVIEW -> RESOLVED after re-certification.
    Preserves the other fields (read-modify-write). Still display-only; the gate ignores it."""
    cur = read_governance_drift()
    if not cur:
        print("resolve: no governance-drift aspect present — nothing to resolve.", file=sys.stderr)
        return None
    cur["status"] = "RESOLVED"
    payload = {DRIFT_KEY: {"data": cur}}
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(payload, f)
    try:
        _run_json([
            "gcloud", "dataplex", "entries", "update-aspects", DP_ENTRY,
            "--entry-group", ENTRY_GROUP, "--location", LOCATION, "--project", PROJECT,
            "--aspects", path,
        ])
    finally:
        os.unlink(path)
    return cur


def main():
    ap = argparse.ArgumentParser(description="Write the DISPLAY-ONLY Governance Drift aspect")
    ap.add_argument("--classification", choices=["cosmetic", "substantive"])
    ap.add_argument("--reasoning")
    ap.add_argument("--recommendation")
    ap.add_argument("--resolve", action="store_true",
                    help="flip status PENDING_REVIEW -> RESOLVED after re-certification")
    a = ap.parse_args()

    if a.resolve:
        data = resolve_governance_drift()
        if data:
            print(f"resolved governance-drift aspect ({DRIFT_KEY}): status={data.get('status')}")
            print(json.dumps(data, indent=2))
        return

    if not (a.classification and a.reasoning and a.recommendation):
        print("provide --classification/--reasoning/--recommendation, or --resolve", file=sys.stderr)
        sys.exit(2)

    tier, dims, drifted_at = read_verification()
    if tier != "unverified":
        print(f"NOTE: verification source_tier is '{tier}', not 'unverified'. The Governance "
              "Drift display aspect is meant for a drifted DP; writing it anyway for the "
              "current state.", file=sys.stderr)
    data = write_governance_drift(dims, drifted_at, a.classification, a.reasoning, a.recommendation)
    print(f"wrote governance-drift aspect ({DRIFT_KEY}):")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
