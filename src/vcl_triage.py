#!/usr/bin/env python3
"""
VCL semantic triage (standalone v1).
Author: Wissem Khlifi ·
July 2026


WHAT IT IS: an ADVISORY tool for the steward. When the deterministic semantic anchor
drifts (business-rules text changed), this compares OLD vs NEW rule text and advises
whether the change is cosmetic or substantive, and which rule(s) changed.


WHAT IT IS NOT: it does NOT decide verification. It never writes source_tier, never
re-seals, never gates an agent. The deterministic hash is still the trigger and the
verdict; this only helps a human decide how urgently to re-certify. Non-determinism in
the LLM is acceptable HERE precisely because a human makes the actual call.


Uses the current google.genai unified SDK (vertexai=True). Model: gemini-2.5-flash
(this is a classification/extraction task - flash is the right cost/latency tier).


Auth: Application Default Credentials (the attached service account in Cloud Run;
`gcloud auth application-default login` locally). Needs roles/aiplatform.user.


Usage (v1 takes both texts explicitly; storing old text in the anchor comes later):
    python3 vcl_triage.py --old-file old_rules.txt --new-file new_rules.txt
    python3 vcl_triage.py --old "..." --new "..."
"""


import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request


from google import genai
from google.genai import types
from dotenv import load_dotenv


# Load repo-root .env so config comes from the environment, not hardcoded literals.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


PROJECT = os.environ.get("VCL_PROJECT", "your-project-id")
LOCATION = os.environ.get("VCL_LOCATION", "us-central1")
MODEL = os.environ.get("VCL_TRIAGE_MODEL", "gemini-2.5-flash")
ASPECT_TYPE = os.environ.get(
    "VCL_ASPECT_TYPE",
    "projects/your-project-number/locations/us-central1/aspectTypes/verification",
)
# Audit store (SEPARATE from the verification aspect — ARCHITECTURE INV-3). A dedicated
# Firestore database + collection; the triage only CREATEs here, never reads it back into
# any verdict path.
AUDIT_DATABASE = os.environ.get("VCL_AUDIT_DATABASE", "vcl-audit")
AUDIT_COLLECTION = os.environ.get("VCL_AUDIT_COLLECTION", "vcl_triage_audit")




def _run_json(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:300])
    return json.loads(p.stdout) if p.stdout.strip() else None




def read_pin(dp_entry, entry_group="@dataplex"):
    """Read the drifted_hash pin + drift_summary from the verification aspect."""
    out = _run_json([
        "gcloud", "dataplex", "entries", "lookup", dp_entry,
        "--entry-group", entry_group, "--location", LOCATION,
        "--project", PROJECT, "--view", "CUSTOM",
        "--aspect-types", ASPECT_TYPE, "--format", "json",
    ])
    for k, v in (out or {}).get("aspects", {}).items():
        if "verification" in k:
            d = v.get("data", {})
            return {"source_tier": d.get("source_tier"),
                    "drift_summary": d.get("drift_summary", []),
                    "drifted_hash": d.get("drifted_hash", ""),
                    "drift_detected_at": d.get("drift_detected_at", ""),
                    "certified_text": d.get("certified_text", "")}
    return None




def current_context_hash(dp_resource):
    """Hash the current composed lookup_context - the same thing the anchor pins."""
    tok = subprocess.run(["gcloud", "auth", "print-access-token"],
                         capture_output=True, text=True).stdout.strip()
    body = json.dumps({
        "method": "tools/call",
        "params": {"name": "lookup_context",
                   "arguments": {"projectId": PROJECT, "location": LOCATION,
                                 "resources": [dp_resource]}},
        "jsonrpc": "2.0", "id": 1,
    }).encode()
    req = urllib.request.Request("https://dataplex.googleapis.com/mcp",
                                 data=body, method="POST")
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("content-type", "application/json")
    req.add_header("accept", "application/json, text/event-stream")
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode()
    outer = json.loads(raw) if raw.lstrip().startswith("{") else \
        json.loads(next(l.strip()[5:].strip() for l in raw.splitlines()
                        if l.strip().startswith("data:")))
    ctx = json.loads(outer["result"]["content"][0]["text"]).get("context", "")
    return ctx, f"sha256:{hashlib.sha256(ctx.encode()).hexdigest()}"




SYSTEM = (
    "You are a data-governance change reviewer. You are given the OLD and NEW text of "
    "a data product's business rules. Your ONLY job is to classify the change and help "
    "a human steward decide whether re-certification needs careful review. You do NOT "
    "make the certification decision. Be conservative: if a change could alter what an "
    "AI agent is permitted to do with the data (e.g. a rule about PII, exposure, "
    "calculation, access, retention), classify it 'substantive' even if the wording "
    "change is small. Only classify 'cosmetic' if the MEANING is unchanged (typos, "
    "formatting, reordering, punctuation). "
    "Respond with ONLY a JSON object, no markdown, no prose, of the form: "
    '{"classification": "cosmetic" | "substantive", '
    '"changed_rules": ["short description of each rule that changed in meaning"], '
    '"reasoning": "one sentence", '
    '"recommendation": "one-click re-approve" | "review carefully before re-certifying"}'
)




def triage(old_text, new_text):
    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    prompt = (
        f"OLD business rules:\n<<<\n{old_text}\n>>>\n\n"
        f"NEW business rules:\n<<<\n{new_text}\n>>>\n\n"
        f"Classify the change per your instructions. JSON only."
    )
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            temperature=0,  # note: temp 0 is stable-ish, NOT provably deterministic.
            # acceptable here because this only ADVISES a human.
        ),
    )
    raw = (resp.text or "").strip()
    # strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if "```" in raw[3:] else raw
        raw = raw.lstrip("json").strip("`").strip()
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError:
        return None, raw




def _write_audit_record(dp_resource, pin, old_text, new_text, advice):
    """BEST-EFFORT: append the triage's advisory record to Firestore (the vcl-audit
    database). This is ADVISORY PROVENANCE, never a verdict (ARCHITECTURE INV-3): it goes
    to a SEPARATE store, is never read by the wrapper's gate or by vcl.py, and must NEVER
    block or alter the advice already produced above. On ANY failure it prints a note and
    returns — the steward still gets the advice.
    """
    try:
        from google.cloud import firestore

        def _h(t):
            return "sha256:" + hashlib.sha256(t.encode()).hexdigest() if t else None

        record = {
            "dp_resource": dp_resource,                       # None in manual (non-gate) mode
            "recorded_at": firestore.SERVER_TIMESTAMP,
            "drifted_hash": (pin or {}).get("drifted_hash") or None,  # version pin, or None
            "pin_available": bool(pin and pin.get("drifted_hash")),   # note when no pin
            "drift_summary": (pin or {}).get("drift_summary"),
            "classification": advice.get("classification"),  # cosmetic | substantive
            "changed_rules": advice.get("changed_rules"),     # LLM advice, verbatim
            "reasoning": advice.get("reasoning"),
            "recommendation": advice.get("recommendation"),
            "model": MODEL,
            "advisory": True,                                 # never mistake this for a verdict
            "certified_text_hash": _h(old_text),              # OLD fingerprint compared
            "current_text_hash": _h(new_text),                # NEW fingerprint compared
        }
        client = firestore.Client(project=PROJECT, database=AUDIT_DATABASE)
        _, ref = client.collection(AUDIT_COLLECTION).add(record)
        print(f"[audit] advisory triage recorded to Firestore "
              f"{AUDIT_DATABASE}/{AUDIT_COLLECTION} (doc {ref.id})")
    except Exception as e:  # noqa: BLE001 - audit is best-effort; the advice must never block
        print(f"[audit write failed: {e}] (the advice above is unaffected)")


def main():
    ap = argparse.ArgumentParser(description="VCL semantic triage (advisory)")
    ap.add_argument("--old")
    ap.add_argument("--new")
    ap.add_argument("--old-file")
    ap.add_argument("--new-file")
    # atomicity-gated mode: verify the pin before advising
    ap.add_argument("--dp-entry", help="DP entry name; enables the atomicity gate")
    ap.add_argument("--dp-resource", help="lookup_context resource name (for the gate)")
    a = ap.parse_args()


    # --- ATOMICITY GATE (optional) ---
    # If --dp-entry/--dp-resource given, verify the CURRENT context still matches the
    # drifted_hash the enforce verdict pinned. Refuse if it moved (someone edited
    # again) - so the triage never advises on a different version than was flagged.
    new_from_gate = None
    old_from_gate = None
    pin = None  # kept in scope for the audit record (set below in gate mode)
    if a.dp_entry and a.dp_resource:
        pin = read_pin(a.dp_entry)
        if pin is None:
            print("GATE: no verification aspect found.", file=sys.stderr); return 2
        if pin["source_tier"] != "unverified" or "semantic" not in pin["drift_summary"]:
            print("GATE: no semantic drift is currently pinned - nothing to triage. "
                  f"(tier={pin['source_tier']}, drift={pin['drift_summary']})")
            return 0
        if not pin["drifted_hash"]:
            print("GATE: semantic drift recorded but no drifted_hash pin "
                  "(sealed before atomicity?). Re-run enforce.", file=sys.stderr)
            return 2
        cur_text, cur_hash = current_context_hash(a.dp_resource)
        if cur_hash != pin["drifted_hash"]:
            print("GATE REFUSED: the context changed again since drift was detected.\n"
                  f"  pinned (drift verdict): {pin['drifted_hash'][:23]}...\n"
                  f"  current now           : {cur_hash[:23]}...\n"
                  "  The triage will NOT advise on a version the verdict is not about.\n"
                  "  Re-run `vcl.py enforce` to re-pin, then triage again.")
            return 3
        print(f"GATE OK: current context matches the pinned drift version "
              f"({cur_hash[:23]}...). Safe to triage.\n")
        new_from_gate = cur_text  # NEW = pinned-and-verified current
        old_from_gate = pin.get("certified_text") or None  # OLD = last-certified text


    old = None
    if a.old is not None:
        old = a.old
    elif a.old_file:
        old = open(a.old_file).read()
    elif old_from_gate:
        old = old_from_gate
        print("(using stored certified_text as the OLD baseline - the exact "
              "last-certified version, not a hand-supplied file)\n")


    if new_from_gate is not None:
        new = new_from_gate
    else:
        new = a.new if a.new is not None else (open(a.new_file).read() if a.new_file else None)
    if old is None or new is None:
        print("provide --old/--new (or --old-file/--new-file); "
              "--new is auto-filled by the atomicity gate when --dp-resource is used.",
              file=sys.stderr)
        return 2


    if old.strip() == new.strip():
        print(json.dumps({"classification": "cosmetic", "changed_rules": [],
                          "reasoning": "texts are identical",
                          "recommendation": "one-click re-approve"}, indent=2))
        return 0


    parsed, raw = triage(old, new)
    if parsed is None:
        print("TRIAGE: model did not return clean JSON. Raw response:")
        print(raw)
        return 1
    print(json.dumps(parsed, indent=2))
    print("\n(ADVISORY ONLY - the steward decides whether to re-seal. "
          "This does not change any verification verdict.)")
    # ADDITIVE (INV-3): record the advice to the separate audit store, best-effort.
    # Runs AFTER the advice is printed and never affects it.
    _write_audit_record(a.dp_resource, pin, old, new, parsed)
    return 0




if __name__ == "__main__":
    sys.exit(main())