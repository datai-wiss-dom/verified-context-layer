#!/usr/bin/env python3
"""
run_demo.py - the runner for the L210 VCL demo.
Author: Wissem Khlifi ·
July 2026

Sends ONE fixed brief to the ONE agent and prints, from the RAW event stream (not the
agent's prose):

  * the raw MCP context the wrapper returned (full governed context, or the withhold note)
  * the SQL the agent authored (the args it passed to execute_audience_sql, if any)
  * the SQL that was actually executed (verified path only)
  * the agent's final response

Run it TWICE with the ONLY difference being the catalog verification state:

  Run A (DP verified)   -> wrapper delivers context -> agent authors a PII-safe query
                           -> action tool executes it -> audience built.
  Run B (DP unverified) -> wrapper withholds context -> action tool refuses
                           -> no audience built; agent explains re-cert is pending.

Prereqs (see vcl_audience_demo/README.md for the full seal/drift sequence):
  export VCL_TOKEN=$(gcloud auth print-access-token)
  python3 src/vcl_wrapper.py            # wrapper running on 127.0.0.1:8080 in another shell
  python3 vcl_audience_demo/run_demo.py
"""

import asyncio
import json
import os

from dotenv import load_dotenv

# Load repo-root .env so all config comes from the environment, not hardcoded literals.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Vertex backend config for gemini-2.5-flash. Set before the agent (and its model) load.
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", os.environ.get("VCL_PROJECT", "your-project-id"))
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", os.environ.get("VCL_LOCATION", "us-central1"))

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import (
    audience_builder_agent,
    execute_audience_sql,
    SANCTIONED_SAMPLE_SQL,
)

APP_NAME = "vcl_audience_demo"
USER_ID = "marketing"

# BigQuery observability (Observability Protocol). Each lesson writes to its own table in
# the shared agent_analytics dataset; the plugin auto-creates the table on first run.
# Guarded so analytics never blocks agent execution.
_ANALYTICS_TABLE = "c2_l210_agent_events"


def _analytics_plugins() -> list:
    try:
        from google.adk.plugins.bigquery_agent_analytics_plugin import (
            BigQueryAgentAnalyticsPlugin,
        )
        return [BigQueryAgentAnalyticsPlugin(
            project_id=os.environ.get("VCL_PROJECT", "your-project-id"),
            dataset_id="agent_analytics",
            table_id=_ANALYTICS_TABLE,
        )]
    except Exception as exc:  # noqa: BLE001 - analytics is best-effort, never blocking
        print(f"[analytics disabled: {exc}]")
        return []

# The fixed brief - IDENTICAL in both runs (challenge.md). The only thing that changes
# between runs is the Data Product's verification state in the catalog.
BRIEF = (
    "Build the win-back campaign audience: high-value customers who have not ordered "
    "in the last 90 days. Produce an audience export the marketing platform can use to "
    "reach them."
)


def _rule(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def _pretty(obj) -> str:
    try:
        return json.dumps(obj, indent=2, default=str)
    except (TypeError, ValueError):
        return str(obj)


async def main() -> None:
    if not os.environ.get("VCL_TOKEN"):
        raise SystemExit(
            "VCL_TOKEN is not set. Run:  export VCL_TOKEN=$(gcloud auth print-access-token)"
        )

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    runner = Runner(app_name=APP_NAME, agent=audience_builder_agent,
                    session_service=session_service, plugins=_analytics_plugins())
    message = types.Content(role="user", parts=[types.Part(text=BRIEF)])

    # Everything below is captured from the RAW event stream - the tool calls/responses -
    # NOT parsed out of the agent's natural-language answer (round-trip discipline, TR-5).
    raw_context = None       # what lookup_context (via the wrapper) returned
    authored_sql = None      # args the agent passed to execute_audience_sql
    action_result = None     # what execute_audience_sql returned
    final_text = None

    _rule("BRIEF (identical both runs)")
    print(BRIEF)

    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=message
    ):
        for call in event.get_function_calls():
            if call.name == "execute_audience_sql":
                authored_sql = (call.args or {}).get("sql")
        for resp in event.get_function_responses():
            if resp.name == "lookup_context":
                raw_context = resp.response
            elif resp.name == "execute_audience_sql":
                action_result = resp.response
        if event.content and event.content.parts:
            for part in event.content.parts:
                txt = getattr(part, "text", None)
                if txt and txt.strip():
                    final_text = txt.strip()

    _rule("1. RAW MCP CONTEXT returned by the VCL wrapper (verified context OR withhold note)")
    if raw_context is None:
        print("(the agent did not call lookup_context)")
    else:
        # The MCP result wraps the payload in content[].text; unwrap for readability.
        printed = False
        try:
            for item in raw_context.get("content", []):
                if item.get("type") == "text":
                    text = item["text"]
                    try:
                        print(_pretty(json.loads(text)))
                    except (json.JSONDecodeError, TypeError):
                        print(text)
                    printed = True
        except AttributeError:
            pass
        if not printed:
            print(_pretty(raw_context))

    _rule("2. SQL the agent AUTHORED (args passed to the action tool)")
    print(authored_sql if authored_sql else "(the agent authored no SQL)")

    _rule("3. SQL that was EXECUTED + result (verified path only)")
    if action_result is None:
        print("(the action tool was not called / nothing executed)")
    else:
        print(_pretty(action_result))

    _rule("4. AGENT FINAL RESPONSE")
    print(final_text if final_text else "(no final text)")

    # --- STRUCTURAL ENFORCEMENT PROBE (identical code in both runs) --------------------
    # Directly hand the action tool a fixed, sanctioned, PII-safe SQL statement - the same
    # statement regardless of run. The tool reads the Data Product's verdict itself:
    #   verified   -> it executes (enforcement lets a governed action through)
    #   unverified -> it refuses (structural: the TOOL declines, no matter the SQL or any
    #                 instruction). This is the criterion-4 proof that enforcement lives
    #                 in the tool, not in the agent's prompt.
    _rule("5. STRUCTURAL ENFORCEMENT PROBE - action tool handed a fixed sanctioned query")
    print("Submitted SQL (same both runs):\n" + SANCTIONED_SAMPLE_SQL + "\n")
    probe = execute_audience_sql(SANCTIONED_SAMPLE_SQL)
    if probe.get("executed"):
        print(f"-> tool EXECUTED it (DP verified): {probe['row_count']} audience rows.")
    else:
        print(f"-> tool DECLINED ({probe.get('status')}): {probe.get('reason')}")


if __name__ == "__main__":
    asyncio.run(main())
