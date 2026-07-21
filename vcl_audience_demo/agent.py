#!/usr/bin/env python3
"""
audience_builder_agent - the ONE agent for the L210 VCL demo.
Author: Wissem Khlifi ·
July 2026

ONE LlmAgent, TWO tools, run twice (verified / unverified). The agent is NAIVE about
VCL: nothing in its instruction checks verification, mentions PII, or tells it to stop.
Both tools enforce governance STRUCTURALLY (Principle 1: structural over instructional):

  Tool 1  vcl_context   - governed context THROUGH the VCL wrapper (McpToolset ->
                          http://127.0.0.1:8080/mcp). The wrapper DELIVERS the customer
                          Data Product's context when the DP is verified, and WITHHOLDS
                          it (honest note, no content) when it has drifted. The agent
                          physically cannot ground on context it never receives.

  Tool 2  execute_audience_sql - the ACTION tool. It reads the DP's verdict itself (the
                          SAME source_tier the wrapper reads) and REFUSES to execute
                          against an unverified DP, regardless of what SQL the agent
                          submits. It is also structurally scoped to the sanctioned SAFE
                          objects only, so it physically cannot touch the PII-bearing
                          `customers` view or any base table.

The ONLY variable between the two runs is the catalog's verification state.
"""

import os
import re

from google.adk.agents import LlmAgent
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPConnectionParams,
)
from google.cloud import bigquery
from dotenv import load_dotenv

# Load repo-root .env so all config comes from the environment, not hardcoded literals.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# The action tool reads the DP verdict via the SAME code the wrapper uses. We load it
# (not re-implement it) so "the same source_tier the wrapper reads" is true by
# construction. Loaded by file path from src/ (which is not on the default import path);
# vcl_wrapper.py only runs a server under __main__, so importing it is side-effect free.
# We do NOT modify it.
import importlib.util as _ilu

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
_spec = _ilu.spec_from_file_location("vcl_wrapper", os.path.join(_SRC, "vcl_wrapper.py"))
_vcl_wrapper = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_vcl_wrapper)
read_source_tier = _vcl_wrapper.read_source_tier


# --- MCP client compatibility shim (does NOT touch the wrapper or any VCL file) -------
# Google's real `lookup_context` advertises an OUTPUT SCHEMA. The strict MCP client
# therefore demands `structuredContent` on every successful result. The wrapper's
# WITHHOLD response is valid MCP - text content, isError=False - but intentionally
# carries NO structured content (there is no data to return; withholding is the point).
# Without this shim the client raises before the honest withhold note can reach the
# agent, and the unverified path looks like a transport error instead of a governance
# decision. We relax validation ONLY for the text-only case; structured (verified)
# results are still validated normally. This is a client-side accommodation of the
# wrapper's behavior, not a change to it.
from mcp.client.session import ClientSession as _ClientSession  # noqa: E402

_orig_validate = _ClientSession._validate_tool_result


async def _lenient_validate_tool_result(self, name, result):
    if getattr(result, "structuredContent", None) is None:
        return  # text-only result (e.g. the VCL withhold note) - accept as-is
    return await _orig_validate(self, name, result)


_ClientSession._validate_tool_result = _lenient_validate_tool_result


# --- configuration (Vertex project + the governed customer Data Product) -------------
PROJECT = os.environ.get("VCL_PROJECT", "your-project-id")
LOCATION = os.environ.get("VCL_LOCATION", "us-central1")

WRAPPER_URL = os.environ.get("VCL_WRAPPER_URL", "http://127.0.0.1:8080/mcp")
TOKEN = os.environ.get("VCL_TOKEN", "")

# The customer Data Product's lookup_context resource name (search_entries
# dataplexEntry.name). This is grounding config - which product to look up - NOT VCL
# awareness. The wrapper decides whether to deliver or withhold its context.
DP_RESOURCE = os.environ.get(
    "VCL_DP_RESOURCE",
    "projects/your-project-number/locations/us-central1/entryGroups/@dataplex/entries/"
    "projects/your-project-number/locations/us-central1/dataProducts/"
    "your-data-product",
)

# The sanctioned SAFE objects the action tool is allowed to touch. customers_safe is the
# PII-safe view (NO email/first_name/last_name by construction); orders is the JOIN
# target. Anything else - the PII-bearing `customers` view, base Iceberg tables - is out
# of scope and structurally refused.
SAFE_VIEW = f"{PROJECT}.ecommerce_views.customers_safe"
ORDERS_VIEW = f"{PROJECT}.ecommerce_views.orders"
ALLOWED_OBJECTS = {SAFE_VIEW, ORDERS_VIEW}


# ============================ TOOL 1: governed context ===============================
# Governed customer context THROUGH the VCL wrapper. Filtered to lookup_context so the
# agent has exactly one, unambiguous way to fetch grounding. The wrapper gates it:
# verified -> full context; unverified -> withheld + honest note.
vcl_context = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=WRAPPER_URL,
        headers={"Authorization": f"Bearer {TOKEN}"},
        timeout=30,
        sse_read_timeout=30,
    ),
    tool_filter=["lookup_context"],
)


# ============================ TOOL 2: the ACTION tool ================================
_TABLE_REF_RE = re.compile(r"`?([A-Za-z0-9_\-]+)`?\.`?([A-Za-z0-9_]+)`?\.`?([A-Za-z0-9_]+)`?")


def _referenced_objects(sql: str) -> set[str]:
    """Extract fully-qualified `project.dataset.table` refs mentioned in the SQL."""
    return {f"{p}.{d}.{t}" for (p, d, t) in _TABLE_REF_RE.findall(sql)}


def execute_audience_sql(sql: str) -> dict:
    """Author-and-execute the marketing audience query.

    Submit a BigQuery SQL SELECT that builds the win-back audience. The tool executes it
    and returns the resulting audience rows.

    Args:
        sql: The BigQuery Standard SQL SELECT statement to run.

    Returns:
        A dict describing the outcome (status, and on success a sample of audience rows).
    """
    # --- STRUCTURAL GATE 1: the DP verdict (the SAME source the wrapper reads) --------
    # Enforcement lives HERE, not in the prompt. If the customer Data Product is not
    # currently verified, this tool refuses to execute - whatever SQL was submitted.
    tier, drifted_dims, err = read_source_tier(DP_RESOURCE)
    if tier != "verified":
        if err:
            reason = err
        elif drifted_dims:
            reason = f"{', '.join(drifted_dims)} drifted - re-certification pending"
        else:
            reason = f"source_tier={tier}"
        return {
            "status": "refused_unverified",
            "executed": False,
            "reason": (
                "The customer Data Product's governance is NOT currently verified "
                f"({reason}). No audience was built or exported. Re-certification by a "
                "steward is required before this action can run."
            ),
        }

    # --- STRUCTURAL GATE 2: scope to the sanctioned SAFE objects only -----------------
    # Even when verified, the tool only touches customers_safe + orders. This makes it
    # physically impossible to select email (customers_safe has none) or to reach the
    # PII-bearing `customers` view / base tables. (Production seam: replace with an
    # IAM-scoped service account that cannot read those objects at all.)
    refs = _referenced_objects(sql)
    disallowed = refs - ALLOWED_OBJECTS
    if disallowed:
        return {
            "status": "refused_out_of_scope",
            "executed": False,
            "reason": (
                "This tool may only query the sanctioned safe objects "
                f"{sorted(ALLOWED_OBJECTS)}. The submitted SQL referenced "
                f"out-of-scope objects: {sorted(disallowed)}."
            ),
        }

    # --- STRUCTURAL GATE 3: never let PII columns into an export (safety, TR-7) --------
    # Defense-in-depth safety net. The safe view has no email column anyway, so a correct
    # query never trips this; it exists so a real leak can never be executed by accident.
    if re.search(r"\bemail\b", sql, re.IGNORECASE):
        return {
            "status": "refused_pii",
            "executed": False,
            "reason": "Refused: the query references an email/PII column; PII must "
                      "never be exported.",
        }

    # --- verified + in-scope + PII-safe: execute for real -----------------------------
    try:
        client = bigquery.Client(project=PROJECT)
        job = client.query(sql)
        rows = list(job.result())
    except Exception as exc:  # noqa: BLE001 - surface the real error to the runner
        return {"status": "execution_error", "executed": False,
                "executed_sql": sql, "reason": str(exc)}

    sample = [dict(r) for r in rows[:10]]
    return {
        "status": "executed",
        "executed": True,
        "executed_sql": sql,
        "row_count": len(rows),
        "audience_sample": sample,
    }


bq_action = FunctionTool(func=execute_audience_sql)

# A sanctioned, PII-safe win-back query used by the runner's structural-enforcement
# probe (identical in both runs). It touches only customers_safe + orders and selects no
# PII, so on the verified path it executes safely; on the unverified path the tool
# refuses it - proving enforcement is in the TOOL (reads the verdict), not the prompt.
SANCTIONED_SAMPLE_SQL = (
    "SELECT c.customer_id, c.customer_segment, ROUND(c.lifetime_value, 2) AS lifetime_value "
    f"FROM `{SAFE_VIEW}` AS c "
    f"LEFT JOIN `{ORDERS_VIEW}` AS o ON c.customer_id = o.customer_id "
    "GROUP BY c.customer_id, c.customer_segment, c.lifetime_value "
    "HAVING MAX(o.order_date) < DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY) "
    "AND c.lifetime_value > 500 "
    "ORDER BY lifetime_value DESC"
)


# ================================== THE AGENT =======================================
# CRITICAL (Principle 1): this instruction contains NO enforcement. It never mentions
# VCL, verification, drift, or PII. It only says: get the context from your tool, build
# strictly from what you receive, and if a tool declines or hands you nothing usable,
# relay that plainly. The gating is done by the TOOLS (Tool 1 withholds, Tool 2 refuses),
# never by trusting the agent to police itself.
audience_builder_agent = LlmAgent(
    name="audience_builder_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You build marketing audiences from customer data by authoring and running SQL.\n"
        "\n"
        "Workflow for any audience request:\n"
        "1. FIRST call `lookup_context` to retrieve the customer data product's "
        "context. Call it with these arguments exactly:\n"
        f"     projectId = \"{PROJECT}\"\n"
        f"     location  = \"{LOCATION}\"\n"
        f"     resources = [\"{DP_RESOURCE}\"]\n"
        "2. Read the returned context. Build your SQL using ONLY the view(s), the JOIN "
        "pattern, the identifier/segment columns, and any rules that context describes. "
        "Do not invent tables, columns, or values it did not give you.\n"
        "3. Call `execute_audience_sql` with your SQL to produce the audience, then "
        "summarize the resulting audience for the user.\n"
        "\n"
        "If a tool returns no usable context, or declines/refuses your request, do not "
        "retry endlessly and do not guess or reconstruct data you were not given. Simply "
        "tell the user plainly what the tool reported - for the customer context that "
        "means explaining the data product's context is pending re-certification and you "
        "therefore have no audience to return."
    ),
    tools=[vcl_context, bq_action],
)

# ADK convention: expose as root_agent so `adk` tooling / App wiring can find it.
root_agent = audience_builder_agent
