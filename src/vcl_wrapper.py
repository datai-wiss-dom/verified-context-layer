#!/usr/bin/env python3
"""
VCL Wrapper - v0.4 STAGE 1: pure passthrough proxy (NO filtering yet).
Author: Wissem Khlifi ·
July 2026


Goal of stage 1: prove the plumbing. This server receives an MCP-shaped
`lookup_context` call, forwards it verbatim to Google's real KC MCP endpoint,
and returns the result unchanged. No verdict reading, no gating. Once this
works, stage 2 adds the input-side gating (drop unverified Data Products).


Run locally:
    export VCL_TOKEN=$(gcloud auth print-access-token)
    python3 vcl_wrapper.py            # serves on http://127.0.0.1:8080/mcp


Test (in another shell):
    curl -s -X POST http://127.0.0.1:8080/mcp \
      -H "content-type: application/json" \
      -d '{"method":"tools/call","params":{"name":"lookup_context",
           "arguments":{"projectId":"your-project-id","location":"us-central1",
           "resources":["<a DP resource name>"]}},"jsonrpc":"2.0","id":1}'


The wrapper reads the bearer token from VCL_TOKEN (so we never hardcode creds).
"""


import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import google.auth
from google.auth.transport.requests import Request as _GoogleAuthRequest
from dotenv import load_dotenv

# Load repo-root .env so config comes from the environment, not hardcoded literals.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


GOOGLE_MCP = "https://dataplex.googleapis.com/mcp"
DATAPLEX_API = "https://dataplex.googleapis.com/v1"


# --- auth: token for Dataplex ------------------------------------------------
# Prefer VCL_TOKEN when set (local dev / explicit override); otherwise use the runtime
# service account's Application Default Credentials (Cloud Run). This is auth ACQUISITION
# only — the gating logic below is unchanged.
_adc_credentials = None


def _get_token():
    explicit = os.environ.get("VCL_TOKEN")
    if explicit:
        return explicit
    global _adc_credentials
    if _adc_credentials is None:
        _adc_credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if not _adc_credentials.valid:
        _adc_credentials.refresh(_GoogleAuthRequest())
    return _adc_credentials.token


# --- config: where verdicts live -------------------------------------------
LOCATION = os.environ.get("VCL_LOCATION", "us-central1")
PROJECT = os.environ.get("VCL_PROJECT", "your-project-id")
ASPECT_TYPE = os.environ.get(
    "VCL_ASPECT_TYPE",
    "projects/your-project-number/locations/us-central1/aspectTypes/verification",
)




def is_data_product(resource_name):
    """A DP resource contains /dataProducts/ in its path."""
    return "/dataProducts/" in resource_name




def read_source_tier(dp_resource):
    """
    Read a Data Product's stored source_tier + drift_summary via CUSTOM-view aspect read.
    Returns (tier, drifted_dims, err). tier is 'verified'/'unverified'/None;
    drifted_dims is a list like ['semantic'] (which dimensions drifted), for the note.
    """
    # Dataplex REST lookupEntry (CUSTOM view, verification aspect) with ADC/VCL_TOKEN.
    # No gcloud dependency; the verdict LOGIC (find source_tier + drift_summary) is unchanged.
    if "/entries/" not in dp_resource:
        return None, [], "not an entry resource"
    params = urllib.parse.urlencode(
        {"entry": dp_resource, "view": "CUSTOM", "aspectTypes": ASPECT_TYPE})
    url = f"{DATAPLEX_API}/projects/{PROJECT}/locations/{LOCATION}:lookupEntry?{params}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {_get_token()}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return None, [], f"verdict read failed: HTTP {e.code} {e.reason}"
    except Exception as e:  # noqa: BLE001
        return None, [], f"verdict read failed: {e}"
    for k, v in data.get("aspects", {}).items():
        if "verification" in k:
            d = v.get("data", {})
            return d.get("source_tier"), d.get("drift_summary", []), None
    return None, [], "no verification aspect on this Data Product"




def call_google_mcp(body_dict, token, extra_headers=None):
    """Forward a JSON-RPC body to Google's KC MCP. Returns (parsed_json, response_headers)."""
    data = json.dumps(body_dict).encode("utf-8")
    req = urllib.request.Request(GOOGLE_MCP, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("content-type", "application/json")
    req.add_header("accept", "application/json, text/event-stream")
    if extra_headers:
        for k, v in extra_headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        hdrs = dict(resp.headers)
        # Google MCP may return SSE-framed data; extract the JSON line if so.
        if raw.lstrip().startswith("{"):
            return json.loads(raw), hdrs
        # SSE: lines like "data: {...}"
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                return json.loads(line[5:].strip()), hdrs
        return json.loads(raw), hdrs  # last resort, will raise if not json




class WrapperHandler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200, extra_headers=None):
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        if extra_headers:
            for k, v in extra_headers.items():
                if v:
                    self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)


    def _passthrough(self, body, token, session_id):
        """Proxy a method to Google unchanged, relaying the session header both ways."""
        extra = {}
        if session_id:
            extra["Mcp-Session-Id"] = session_id
        result, hdrs = call_google_mcp(body, token, extra)
        return result, hdrs.get("Mcp-Session-Id") or hdrs.get("mcp-session-id")


    def do_POST(self):
        if self.path != "/mcp":
            self._send({"error": "not found"}, 404)
            return


        length = int(self.headers.get("content-length", 0))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self._send({"error": "invalid json"}, 400)
            return


        try:
            token = _get_token()
        except Exception as e:  # noqa: BLE001
            self._send({"error": f"could not obtain credentials: {e}"}, 500)
            return


        # session id the client sent us (if mid-session)
        client_session = self.headers.get("Mcp-Session-Id")


        method = body.get("method", "")


        # Notifications (no id) get no response body per JSON-RPC; relay and 202.
        is_notification = "id" not in body
        if is_notification:
            try:
                self._passthrough(body, token, client_session)
            except Exception as e:
                print("wrapper: notification relay failed:", e)
            self.send_response(202)
            self.end_headers()
            return


        # Everything EXCEPT a lookup_context tools/call is a clean proxy
        # (initialize, tools/list, other tools). This is what lets an agent connect.
        is_lookup = (method == "tools/call"
                     and body.get("params", {}).get("name") == "lookup_context")
        if not is_lookup:
            try:
                result, new_session = self._passthrough(body, token, client_session)
            except Exception as e:
                self._send({"jsonrpc": "2.0", "id": body.get("id"),
                            "error": {"message": f"upstream failed: {e}"}}, 502)
                return
            extra = {"Mcp-Session-Id": new_session} if new_session else None
            self._send(result, extra_headers=extra)
            return


        # --- STAGE 2: input-side gating on lookup_context ---
        args = body["params"]["arguments"]
        requested = args.get("resources", [])
        verified, excluded = [], []
        for r in requested:
            if not is_data_product(r):
                verified.append(r)  # non-DP resources out of scope for v0.4
                continue
            tier, drifted_dims, err = read_source_tier(r)
            if tier == "verified":
                verified.append(r)
            else:
                if err:
                    reason = err
                elif drifted_dims:
                    reason = (f"{', '.join(drifted_dims)} drifted - "
                              f"re-certification pending")
                else:
                    reason = f"source_tier={tier}"
                excluded.append((r, reason))
                print(f"wrapper: DROP {r.split('/')[-1]} ({reason})")


        note_lines = [f"  - {r.split('/')[-1]}: {reason}"
                      for r, reason in excluded]


        # The note tells the agent the STATE (unverified + why) so it can respond
        # honestly to the user, NOT guess, and NOT fabricate. The structural
        # guarantee is the WITHHELD CONTENT (absent, so ungroundable); this note is
        # advisory context so a well-behaved agent degrades gracefully.
        def build_withhold_note(header):
            return (
                    f"{header}\n"
                    f"VERIFICATION STATUS: unverified.\n"
                    f"The Verified Context Layer withheld the grounding context for the "
                    f"following data product(s) because their certification is no longer "
                    f"current:\n"
                    + "\n".join(note_lines) + "\n"
                                              f"Do not ground on, infer, or fabricate details about the withheld "
                                              f"resource(s). If the user asks about them, explain that the data "
                                              f"product's context is pending re-certification and cannot be used "
                                              f"until a steward re-verifies it."
            )


        if not verified:
            note = build_withhold_note(
                "VCL: all requested resources were withheld.")
            self._send({"jsonrpc": "2.0", "id": body.get("id"),
                        "result": {"content": [{"type": "text", "text": note}],
                                   "isError": False}})
            return


        gated_body = dict(body)
        gated_body["params"] = dict(body["params"])
        gated_body["params"]["arguments"] = dict(args)
        gated_body["params"]["arguments"]["resources"] = verified


        try:
            result, new_session = self._passthrough(gated_body, token, client_session)
        except Exception as e:
            self._send({"jsonrpc": "2.0", "id": body.get("id"),
                        "error": {"message": f"upstream failed: {e}"}}, 502)
            return


        if note_lines:
            appended = build_withhold_note(
                "# VCL: some requested resources were withheld.")
            try:
                inner = json.loads(result["result"]["content"][0]["text"])
                inner["context"] = (inner.get("context", "")
                                    + "\n\n" + appended)
                result["result"]["content"][0]["text"] = json.dumps(inner)
            except (KeyError, IndexError, json.JSONDecodeError):
                result.setdefault("result", {}).setdefault("content", []).append(
                    {"type": "text", "text": appended})


        extra = {"Mcp-Session-Id": new_session} if new_session else None
        self._send(result, extra_headers=extra)


    def log_message(self, fmt, *args):
        # quiet default logging; print a short line instead
        print("wrapper:", fmt % args)




def main():
    # Cloud Run sets PORT; locally fall back to VCL_PORT (default 8080). Bind 0.0.0.0 so
    # Cloud Run can route to the container (127.0.0.1 would be unreachable there); locally
    # loopback clients (the demo agent on 127.0.0.1) still connect fine.
    port = int(os.environ.get("PORT", os.environ.get("VCL_PORT", "8080")))
    host = os.environ.get("VCL_HOST", "0.0.0.0")
    server = HTTPServer((host, port), WrapperHandler)
    print(f"VCL wrapper on http://{host}:{port}/mcp")
    print("forwarding to", GOOGLE_MCP)
    print("auth mode:", "VCL_TOKEN" if os.environ.get("VCL_TOKEN") else "ADC (service account)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")




if __name__ == "__main__":
    main()