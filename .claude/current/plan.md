# Plan — Campaign audience-building agent (build steps)
**Author:** Wissem Khlifi ·

**July 2026**

Follow in order. The MCP wiring symbols below were VERIFIED against the installed ADK
in this venv (2026-07-20). Symbols NOT yet verified are flagged [VERIFY] — check them
against the installed version before use; do not guess.


## Verified wiring facts (do NOT change)
- `McpToolset` from `google.adk.tools.mcp_tool.mcp_toolset`
- `StreamableHTTPConnectionParams` from
  `google.adk.tools.mcp_tool.mcp_session_manager`
  fields (verified): url, headers, timeout, sse_read_timeout, terminate_on_close,
  httpx_client_factory
- Wrapper is a remote HTTP MCP server at http://127.0.0.1:8080/mcp; bearer auth header
  Authorization: Bearer <VCL_TOKEN>. Use StreamableHTTP (NOT Stdio/Sse).
- Model gemini-2.5-flash, Vertex (agentic-2026-493108, us-central1).


## [VERIFY] before building (read the installed API, don't guess)
- ADK Runner + session invocation: `google.adk.runners` — confirm the class and the
  one-shot invoke/run signature in THIS version.
- BigQuery action tool: confirm whether to use ADK's built-in BigQuery toolset
  (check `google.adk.tools` for a bigquery tool) OR a FunctionTool wrapping the
  bigquery python client. Verify the exact import before wiring.
- LlmAgent import path: `from google.adk.agents import LlmAgent` [VERIFY].


## Step 1 — scaffold
Create `vcl_audience_demo/`:
- `agent.py`     (LlmAgent + VCL McpToolset + BigQuery action tool)
- `run_demo.py`  (runner: one fixed brief; prints response + raw MCP context + authored SQL)
  Use `uv add` (not pip) for any deps. Keep it minimal and readable; do not over-scaffold.


## Step 2 — agent.py: two tools, no VCL awareness
```python
import os
from google.adk.agents import LlmAgent   # [VERIFY path]
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
# BigQuery action tool import: [VERIFY] - ADK built-in bigquery toolset OR FunctionTool


WRAPPER_URL = os.environ.get("VCL_WRAPPER_URL", "http://127.0.0.1:8080/mcp")
TOKEN = os.environ["VCL_TOKEN"]


# Tool 1: governed context, THROUGH the VCL wrapper (gated)
vcl_context = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=WRAPPER_URL,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
)


# Tool 2: the ACTION tool - author/execute BigQuery, ENFORCES STRUCTURALLY (option B-light).
# [VERIFY the exact ADK construct: built-in bigquery toolset OR FunctionTool]
# ENFORCEMENT LIVES HERE, NOT IN THE PROMPT. The tool itself reads the DP's verdict
# (source_tier, via the same CUSTOM-view aspect read the wrapper uses) and REFUSES to
# execute if the DP is NOT verified - regardless of what SQL the agent submits. The
# agent cannot make it act on unverified data by any instruction. Implement as a
# FunctionTool(sql) that: (1) reads source_tier for the customer DP; (2) if not
# 'verified' -> return a refusal (no execution); (3) if verified -> execute the SQL,
# but only against the safe view (target must be the handed customers_safe).
# Real objects (verified live 2026-07-20):
#   safe view : agentic-2026-493108.ecommerce_views.customers_safe
#               [customer_id, country, city, signup_date, customer_segment, lifetime_value]
#   join      : agentic-2026-493108.ecommerce_views.orders
#   LOCKED OUT: ecommerce_views.customers (has email), base Iceberg tables
# Two structural layers: (a) customers_safe has no email by construction;
#   (b) the tool refuses entirely when the DP is unverified.
# bq_tool = <FunctionTool: read verdict -> refuse if unverified -> else execute on safe view>


audience_builder_agent = LlmAgent(
    name="audience_builder_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You build marketing audiences from customer data. To do so, first retrieve "
        "the customer data product's context using your context tool, then author SQL "
        "using only the safe view, JOIN pattern, identifiers, and segment values that "
        "context describes. Execute it with your BigQuery tool to produce the audience. "
        "Your tools enforce governance themselves: if a tool declines or returns no "
        "usable context, simply relay to the user that the customer context is pending "
        "re-certification and that you therefore have no audience to return. Do not "
        "speculate about or reconstruct customer data you did not receive from a tool."
    ),
    # NOTE: this instruction contains NO enforcement. It does not say "you MUST NOT
    # query if withheld" - that would be instructional enforcement (Principle-1 failure).
    # Both tools enforce structurally (Tool 1 withholds; Tool 2 refuses on unverified).
    # The instruction only tells the agent how to EXPLAIN a tool's refusal to the user.
    tools=[vcl_context],  # add bq_tool once verified
)
```
CRITICAL (Principle 1): the instruction NEVER mentions VCL, verification state, or
"check if verified". It only says: build strictly from the context you receive; if none,
do not act. The wrapper does the gating structurally by withholding.


## Step 3 — run_demo.py: one brief, show everything
- Invoke the agent once with the fixed brief (exercise.md) via ADK Runner [VERIFY API].
- Print: (a) agent final response, (b) the RAW MCP result the context tool returned
  (real context vs withhold note), (c) the SQL the agent authored (if any).
- On the verified path, allow execution; on withhold, expect no SQL authored.


## Step 4 — prove Run A (verified, executes safe path)
1. Seal/verify the DP: `python3 vcl.py seal <standard args>` (VCL_operations_reference.md).
2. Start wrapper: `export VCL_TOKEN=$(gcloud auth print-access-token); python3 vcl_wrapper.py`
3. In the runner shell: `export VCL_TOKEN=...; python3 vcl_audience_demo/run_demo.py`
4. VERIFY (round-trip): raw context contains the PII rule + JOIN + segment enum; the
   authored SQL EXCLUDES email, uses the sanctioned JOIN, applies the 90-day filter, and
   executed to produce an audience. Capture output.


## Step 5 — prove Run B (unverified, builds nothing)
1. Drift semantic: edit the DP description in the UI, then `python3 vcl.py enforce
   <standard args>` -> confirm source_tier=unverified, drift_summary=['semantic'].
2. Re-run `python3 vcl_audience_demo/run_demo.py` (SAME agent, SAME brief — change nothing).
3. VERIFY (round-trip): raw result is the withhold note; the agent authored/executed
   NOTHING and declined. Capture output.


## Step 6 — restore + record
1. Re-seal clean: `python3 vcl.py seal <standard args>`.
2. Save both captures (A: governed audience built; B: export declined) as demo evidence.


## Safety (mandatory - from requirements TR-7)
- NEVER execute a query selecting email into an export. Verified path is safe by
  construction; unverified path executes nothing. Demonstrate the leak risk by CONTRAST
  (show the safe authored SQL; describe what ungoverned would have written), not by a
  real leak.


## Guardrails
- Do NOT modify vcl.py / vcl_wrapper.py / vcl_triage.py.
- One agent, run twice. No router/second agent/saga.
- No VCL/verification logic in the agent instruction — the wrapper gates.
- VERIFY every [VERIFY]-flagged ADK API against the installed version before use. The
  McpToolset + StreamableHTTPConnectionParams wiring is already verified; the Runner,
  BigQuery tool, and LlmAgent import path are NOT — check them.
- Trust the raw tool result and the actual authored SQL, not the agent's prose.
