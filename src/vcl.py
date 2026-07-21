#!/usr/bin/env python3
"""
Verified Context Layer - validator v0.3c (multi-asset, anchor-list)
Author: Wissem Khlifi ·
July 2026


Deterministic. No LLM. No agent.


MODEL:
  A Data Product declares its own assets (in its data-product aspect). The
  validator reads that manifest - it does NOT take the source by hand.


  seal    : walk the Data Product's assets[]; for each, capture the current
            technical fingerprint (BigQuery etag); write the anchors[] list.
  check   : read anchors[]; for each, re-read the current fingerprint, compare
            to what was sealed; verdict = AND across all anchors; name which
            asset drifted. Writes nothing.
  enforce : check + write the rolled-up source_tier back.


Scope of this version: technical dimension only (fingerprint = BQ etag).
quality/semantic anchors come later; the anchor structure already holds them.


Shells to gcloud/bq (proven auth path); avoids the SDK camelCase-Struct scar.
"""


import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone




def run_json(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{p.stderr.strip()}")
    return json.loads(p.stdout) if p.stdout.strip() else None




def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")




def asset_to_bq_ref(asset_name):
    """
    Parse a Data Product asset 'name' into a bq show reference P:D.T.
    Input:  //bigquery.googleapis.com/projects/P/datasets/D/tables/T
    Output: P:D.T   (or None if not a recognizable BigQuery path)
    """
    marker = "/projects/"
    if "bigquery.googleapis.com" not in asset_name or marker not in asset_name:
        return None
    tail = asset_name.split(marker, 1)[1]
    parts = tail.split("/")
    try:
        proj = parts[0]
        dset = parts[parts.index("datasets") + 1]
        tbl = parts[parts.index("tables") + 1]
    except (ValueError, IndexError):
        return None
    return f"{proj}:{dset}.{tbl}"




def read_dp_assets(project, location, entry_group, dp_entry):
    out = run_json([
        "gcloud", "dataplex", "entries", "lookup", dp_entry,
        "--entry-group", entry_group, "--location", location,
        "--project", project, "--view", "FULL", "--format", "json",
    ])
    for k, v in (out or {}).get("aspects", {}).items():
        if "data-product" in k:
            return v.get("data", {}).get("assets", [])
    return []




def read_claim(project, location, entry_group, dp_entry, aspect_type_fqn):
    out = run_json([
        "gcloud", "dataplex", "entries", "lookup", dp_entry,
        "--entry-group", entry_group, "--location", location,
        "--project", project, "--view", "CUSTOM",
        "--aspect-types", aspect_type_fqn, "--format", "json",
    ])
    for k, v in (out or {}).get("aspects", {}).items():
        if "verification" in k:
            return v.get("data", {})
    return None




def live_etag(bq_ref):
    p = subprocess.run(["bq", "show", "--format=prettyjson", bq_ref],
                       capture_output=True, text=True)
    if p.returncode != 0:
        if "Not found" in p.stderr or "not found" in p.stderr:
            return "DEAD_POINTER"
        raise RuntimeError(f"bq show failed for {bq_ref}: {p.stderr.strip()}")
    return json.loads(p.stdout).get("etag")




def read_scan_quality(project, location, scan_id):
    """
    Read a DATA_QUALITY scan's latest result.
    Returns (passed: bool|None, last_run_iso: str|None, resource: str|None, err: str|None).
    resource = the actual table the scan runs on (data.resource) - what was measured.
    """
    try:
        d = run_json([
            "gcloud", "dataplex", "datascans", "describe", scan_id,
            "--location", location, "--project", project,
            "--view", "FULL", "--format", "json",
        ])
    except RuntimeError as e:
        if "NOT_FOUND" in str(e) or "not found" in str(e).lower():
            return None, None, None, "scan not found"
        raise
    r = (d or {}).get("dataQualityResult", {})
    passed = r.get("passed")
    es = (d or {}).get("executionStatus", {})
    resource = (d or {}).get("data", {}).get("resource")
    if passed is None:
        return None, None, resource, "scan has no dataQualityResult (never run?)"
    # executionStatus fields are NOT guaranteed present: latestJobEndTime can be
    # absent even for an ACTIVE scan with a passing result (observed live). Prefer
    # endTime; fall back to createTime; if neither exists, refuse (no None fingerprint).
    end_time = es.get("latestJobEndTime")
    create_time = es.get("latestJobCreateTime")
    if end_time:
        return passed, ("end", end_time), resource, None
    if create_time:
        return passed, ("create", create_time), resource, None
    return None, None, resource, "scan has result but no usable job timestamp"




def quality_fingerprint(passed, last_run):
    """
    Canonical quality fingerprint: PASS|FAIL @ <source>:<runtime>.
    last_run is a (source, iso) tuple; source is 'end' or 'create'. Encoding the
    source means a check compares like-with-like and won't false-drift merely because
    the timestamp field that was available changed between seal and check.
    """
    src, iso = last_run
    return f"{'PASS' if passed else 'FAIL'}@{src}:{iso}"




def hours_since(iso_ts):
    """Whole hours between iso_ts and now (UTC). None if unparseable."""
    if not iso_ts:
        return None
    try:
        ts = iso_ts.replace("Z", "+00:00")
        # trim fractional seconds beyond 6 digits if present
        dt = datetime.fromisoformat(ts)
    except ValueError:
        # fallback: cut nanoseconds
        base = iso_ts.split(".")[0].replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(base + "+00:00" if "+" not in base else base)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0




def read_business_rules(project, location, entry_group, dp_entry, dp_resource=None):
    """
    Fingerprint the COMPOSED lookup_context context for this Data Product - i.e.
    exactly what an agent grounds on. Returns (text, sha, err).


    Why the composed context, not entrySource.description alone: the agent's grounding
    blends the immutable `description` (holds the PII rule) AND the UI-editable
    `documentation` field. Fingerprinting only the description would miss drift in the
    documentation (regenerate docs -> bad instruction -> agent grounds on it -> anchor
    wrongly reports verified). The composed lookup_context output covers both, and is
    the true grounding surface.


    dp_entry here is the bare DP entry (as passed on the CLI). lookup_context needs the
    full search_entries-style resource name; build it from the entry-group path.
    """
    import urllib.request


    # token via gcloud (consistent with the rest of vcl.py's auth)
    tok = subprocess.run(["gcloud", "auth", "print-access-token"],
                         capture_output=True, text=True)
    if tok.returncode != 0:
        return "", None, f"token fetch failed: {tok.stderr.strip()[:120]}"
    token = tok.stdout.strip()


    # full resource name lookup_context expects (same value search_entries returns).
    # Passed in explicitly to avoid guessing project-id-vs-number nesting.
    if not dp_resource:
        return "", None, "no dp_resource supplied for semantic lookup"
    resource = dp_resource


    body = json.dumps({
        "method": "tools/call",
        "params": {"name": "lookup_context",
                   "arguments": {"projectId": project, "location": location,
                                 "resources": [resource]}},
        "jsonrpc": "2.0", "id": 1,
    }).encode()


    req = urllib.request.Request("https://dataplex.googleapis.com/mcp",
                                 data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("content-type", "application/json")
    req.add_header("accept", "application/json, text/event-stream")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
    except Exception as e:
        return "", None, f"lookup_context call failed: {e}"


    # parse JSON or SSE-framed
    outer = None
    if raw.lstrip().startswith("{"):
        outer = json.loads(raw)
    else:
        for line in raw.splitlines():
            if line.strip().startswith("data:"):
                outer = json.loads(line.strip()[5:].strip())
                break
    if not outer or "result" not in outer:
        return "", None, "lookup_context returned no result"
    try:
        ctx = json.loads(outer["result"]["content"][0]["text"]).get("context", "")
    except (KeyError, IndexError, json.JSONDecodeError):
        return "", None, "unexpected lookup_context shape"
    if not ctx:
        return "", None, "composed context is empty"
    sha = hashlib.sha256(ctx.encode()).hexdigest()
    return ctx, sha, None




def write_claim(args, claim):
    short_key = f"{args.project_number}.{args.location}.verification"
    payload = {short_key: {"data": claim}}
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(payload, f)
    try:
        run_json([
            "gcloud", "dataplex", "entries", "update-aspects", args.dp_entry,
            "--entry-group", args.entry_group, "--location", args.location,
            "--project", args.project, "--aspects", path,
        ])
    finally:
        os.unlink(path)




def current_fingerprint(dimension, asset_name):
    if dimension == "technical":
        bq_ref = asset_to_bq_ref(asset_name)
        if bq_ref is None:
            return None, "asset is not a recognizable BigQuery ref"
        etag = live_etag(bq_ref)
        if etag == "DEAD_POINTER":
            return "DEAD_POINTER", "source did not resolve"
        return etag, None
    return None, f"dimension '{dimension}' not implemented"




def _asset_key(asset_name):
    """Short key for matching a check-time quality-scan mapping to an asset."""
    return asset_name.split("/")[-1] or asset_name




def parse_quality_map(entries):
    """
    --quality-scan 'customers=customers--quality:24' (repeatable)
    Returns { asset_substring: (scan_id, sla_hours) }.
    """
    m = {}
    for e in entries or []:
        if "=" not in e:
            raise ValueError(f"bad --quality-scan '{e}', expected ASSET=SCAN:HOURS")
        asset_key, rest = e.split("=", 1)
        if ":" not in rest:
            raise ValueError(f"bad --quality-scan '{e}', expected SCAN:HOURS after '='")
        scan_id, hours = rest.rsplit(":", 1)
        m[asset_key.strip()] = (scan_id.strip(), int(hours))
    return m




def seal(args):
    assets = read_dp_assets(args.project, args.location, args.entry_group, args.dp_entry)
    if not assets:
        print("SEAL: no assets found on this Data Product - nothing to certify")
        return 2


    qmap = parse_quality_map(args.quality_scan)
    anchors = []
    print(f"SEAL: found {len(assets)} asset(s)")
    for a in assets:
        name = a.get("name", "")
        short = name.split("/")[-1] or name


        # --- technical anchor ---
        fp, err = current_fingerprint("technical", name)
        if err or fp in (None, "DEAD_POINTER"):
            print(f"  SKIP technical {short} ({err or 'no fingerprint'})")
        else:
            print(f"  seal technical {short} = {fp}")
            anchors.append({"asset": name, "dimension": "technical",
                            "fingerprint": fp,
                            "measured_against": name})  # technical reads the view itself


        # --- quality anchor (only if a scan is mapped to this asset) ---
        match = next((v for k, v in qmap.items() if k in name), None)
        if match:
            scan_id, sla = match
            passed, last_run, resource, qerr = read_scan_quality(
                args.project, args.location, scan_id)
            if qerr:
                print(f"  SKIP quality  {short} (scan '{scan_id}': {qerr})")
            else:
                qfp = quality_fingerprint(passed, last_run)
                print(f"  seal quality  {short} = {qfp}  (sla {sla}h)")
                print(f"       measured_against = {resource}")
                anchors.append({"asset": name, "dimension": "quality",
                                "fingerprint": qfp, "freshness_sla_hours": sla,
                                "measured_against": resource or scan_id})


    if not anchors:
        print("SEAL: no anchors could be captured - aborting (nothing sealed)")
        return 1


    # --- semantic anchor: fingerprint the business-rules text (once per DP) ---
    sem_text, sem_sha, sem_err = read_business_rules(
        args.project, args.location, args.entry_group, args.dp_entry, args.dp_resource)
    certified_text = None
    if sem_err:
        print(f"  SKIP semantic ({sem_err})")
    else:
        print(f"  seal semantic (business rules) = sha256:{sem_sha[:16]}...")
        anchors.append({"asset": args.dp_entry, "dimension": "semantic",
                        "fingerprint": f"sha256:{sem_sha}",
                        "measured_against": args.dp_entry})
        certified_text = sem_text  # store the exact text the semantic anchor hashed


    claim = {
        "verified_at": now_iso(),
        "source_tier": "verified",
        "anchors": anchors,
        "verified_against": anchors[0]["asset"],
        "source_etag": anchors[0]["fingerprint"],
        "drift_summary": [],
        "drifted_hash": "",
        # drift_detected_at omitted entirely: it's a datetime and cannot be "".
        # Absent means "no drift pin" (KC preserves absent optional fields).
    }
    if certified_text is not None:
        claim["certified_text"] = certified_text
    write_claim(args, claim)
    print(f"SEAL: wrote {len(anchors)} anchor(s), source_tier=verified.")
    return 0




def evaluate(args):
    claim = read_claim(args.project, args.location, args.entry_group,
                       args.dp_entry, args.aspect_type)
    if claim is None:
        print("RESULT: NO_CLAIM (no verification aspect)")
        return "NO_CLAIM", [], None


    anchors = claim.get("anchors", [])
    if not anchors:
        print("RESULT: NO_ANCHORS (claim has no anchors[] - sealed with an older version?)")
        return "NO_ANCHORS", [], claim


    print(f"verified_at : {claim.get('verified_at')}")
    print(f"stored tier : {claim.get('source_tier')}")
    print(f"anchors     : {len(anchors)}")


    drift = []
    for anc in anchors:
        name = anc.get("asset", "")
        dim = anc.get("dimension", "")
        sealed_fp = anc.get("fingerprint", "")
        sla = anc.get("freshness_sla_hours", 0)
        short = name.split("/")[-1] or name


        if dim == "technical":
            cur_fp, err = current_fingerprint("technical", name)
            if err:
                print(f"  ? {short} [technical] : {err} -> drift")
                drift.append((name, dim, "error"))
            elif cur_fp == "DEAD_POINTER":
                print(f"  x {short} [technical] : DEAD POINTER")
                drift.append((name, dim, "dead_pointer"))
            elif cur_fp != sealed_fp:
                print(f"  ! {short} [technical] : DRIFT ({sealed_fp} -> {cur_fp})")
                drift.append((name, dim, "drift"))
            else:
                print(f"  ok {short} [technical] : matches ({sealed_fp})")


        elif dim == "quality":
            # quality drift = fingerprint changed (pass->fail or new run failed)
            #                 OR stale (current passing result older than SLA)
            scan_id = args.qcheck_map.get(_asset_key(name))
            if not scan_id:
                print(f"  ? {short} [quality] : no scan mapping supplied at check "
                      f"(--quality-scan) -> cannot verify -> drift")
                drift.append((name, dim, "no_scan_map"))
                continue
            passed, last_run, resource, qerr = read_scan_quality(
                args.project, args.location, scan_id)
            if qerr:
                print(f"  ? {short} [quality] : {qerr} -> drift")
                drift.append((name, dim, "scan_error"))
                continue
            cur_fp = quality_fingerprint(passed, last_run)
            age = hours_since(last_run[1])  # last_run is (source, iso)
            # condition 1: not passing, or result identity changed
            if not passed:
                print(f"  ! {short} [quality] : FAILING now ({cur_fp})")
                drift.append((name, dim, "failing"))
            # condition 2: stale - passing result older than SLA.
            # NOTE: sla==0 is a VALID strict threshold (must be ~now), not "no SLA".
            # Use 'is not None', never truthiness, or 0 silently disables the check.
            elif age is not None and age > sla:
                print(f"  ! {short} [quality] : STALE (last run {age:.1f}h ago > SLA {sla}h)")
                drift.append((name, dim, "stale"))
            else:
                agestr = f"{age:.1f}h ago" if age is not None else "age unknown"
                print(f"  ok {short} [quality] : passing, fresh ({agestr}, SLA {sla}h)")


        elif dim == "semantic":
            # semantic drift = business-rules text changed since certification
            _, cur_sha, sem_err = read_business_rules(
                args.project, args.location, args.entry_group, args.dp_entry, args.dp_resource)
            if sem_err:
                print(f"  ? {short} [semantic] : {sem_err} -> drift")
                drift.append((name, dim, "error"))
            else:
                cur_fp = f"sha256:{cur_sha}"
                if cur_fp != sealed_fp:
                    print(f"  ! {short} [semantic] : DRIFT (rules text changed)")
                    drift.append((name, dim, "drift"))
                else:
                    print(f"  ok {short} [semantic] : business rules unchanged")


        else:
            print(f"  ? {short} [{dim}] : unknown dimension -> drift")
            drift.append((name, dim, "unknown_dim"))


    if drift:
        print(f"VERDICT: UNVERIFIED ({len(drift)} of {len(anchors)} anchor(s) drifted)")
        return "UNVERIFIED", drift, claim
    print("VERDICT: VERIFIED (all anchors match)")
    return "VERIFIED", [], claim




def check(args):
    verdict, _, _ = evaluate(args)
    return {"VERIFIED": 0, "UNVERIFIED": 1,
            "NO_CLAIM": 2, "NO_ANCHORS": 2}.get(verdict, 3)




def enforce(args):
    verdict, drift, claim = evaluate(args)
    if verdict in ("NO_CLAIM", "NO_ANCHORS"):
        return 2
    target = "verified" if verdict == "VERIFIED" else "unverified"
    current = claim.get("source_tier", "?")


    drifted_dims = sorted({d[1] for d in drift}) if target == "unverified" else []


    # Atomicity pin: if semantic drifted, capture the CURRENT composed-context hash.
    # This pins the exact version the drift verdict is about, so the triage can refuse
    # to advise on a different version. Hashes only - no text stored.
    pin_hash = None
    if "semantic" in drifted_dims:
        _, cur_sha, sem_err = read_business_rules(
            args.project, args.location, args.entry_group, args.dp_entry, args.dp_resource)
        if not sem_err:
            pin_hash = f"sha256:{cur_sha}"


    if current == target and claim.get("drift_summary", []) == drifted_dims \
            and claim.get("drifted_hash") == pin_hash:
        print(f"ENFORCE: no change (already '{target}', pin current)")
        return 0 if verdict == "VERIFIED" else 1


    print(f"ENFORCE: source_tier '{current}' -> '{target}' ...")
    claim["source_tier"] = target
    claim["drift_summary"] = drifted_dims
    if drifted_dims:
        print(f"ENFORCE: drift_summary = {drifted_dims}")
    if "semantic" in drifted_dims and pin_hash:
        claim["drifted_hash"] = pin_hash
        claim["drift_detected_at"] = now_iso()
        print(f"ENFORCE: drifted_hash pin = {pin_hash[:23]}...")
    else:
        # not a semantic drift (or verified) -> clear any stale pin.
        # drift_detected_at is a datetime and cannot be "" -> remove the key.
        claim["drifted_hash"] = ""
        claim.pop("drift_detected_at", None)
    write_claim(args, claim)
    print("ENFORCE: written. Confirm via CUSTOM read / UI.")
    return 0 if verdict == "VERIFIED" else 1




def build_parser():
    p = argparse.ArgumentParser(description="Verified Context Layer validator (v0.3c + quality)")
    p.add_argument("mode", choices=["seal", "check", "enforce"])
    p.add_argument("--project", required=True)
    p.add_argument("--project-number", required=True,
                   help="project NUMBER, used in the aspect key for writes")
    p.add_argument("--location", default="us-central1")
    p.add_argument("--entry-group", default="@dataplex")
    p.add_argument("--dp-entry", required=True,
                   help="full resource name of the Data Product entry")
    p.add_argument("--dp-resource", default=None,
                   help="the lookup_context resource name (search_entries "
                        "dataplexEntry.name) for the semantic anchor; if omitted, "
                        "the semantic anchor is skipped")
    p.add_argument("--aspect-type", required=True,
                   help="full resource name of the verification aspect type")
    p.add_argument("--quality-scan", action="append", default=[],
                   help="ASSET=SCAN_ID:SLA_HOURS  (repeatable). "
                        "ASSET is a substring matched against the asset name. "
                        "Needed at seal (to capture) and at check/enforce (to re-read).")
    return p




def _build_qcheck_map(quality_scan):
    """For check/enforce: map short asset key -> scan_id (drop SLA, it's in the anchor)."""
    out = {}
    for e in quality_scan or []:
        asset_key, rest = e.split("=", 1)
        scan_id = rest.rsplit(":", 1)[0]
        out[asset_key.strip()] = scan_id.strip()
    # also index by any asset whose name contains the key, resolved lazily in evaluate
    return out




if __name__ == "__main__":
    args = build_parser().parse_args()
    # for check/enforce, build the asset->scan lookup used in the quality branch
    raw = _build_qcheck_map(args.quality_scan)
    # evaluate looks up by _asset_key(name); allow substring match too
    class _Map(dict):
        def get(self, k, default=None):
            if k in self:
                return self[k]
            for kk, vv in self.items():
                if kk in k:
                    return vv
            return default
    args.qcheck_map = _Map(raw)
    fn = {"seal": seal, "check": check, "enforce": enforce}[args.mode]
    sys.exit(fn(args))