# L210 Implementation Plan

## Step 1: Scaffold Project and Install Dependencies

Create the project directory `vcl_audience_demo` and the necessary empty files `agent.py` and `run_demo.py`. Install required Python packages using `uv add`.

```bash
mkdir vcl_audience_demo
touch vcl_audience_demo/agent.py
touch vcl_audience_demo/run_demo.py
uv add google-cloud-bigquery google-generativeai google-cloud-aiplatform google-adk httpx
```

## Step 2: Implement `agent.py` - Initial Agent and MCP Tool

Implement the basic `LlmAgent` structure, including the `McpToolset` for governed context retrieval. This step defines the agent's instruction and its first tool.

```python
# vcl_audience_demo/agent.py
import os
import httpx
import json
from google.adk.agents import LlmAgent # [VERIFY path]
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.function_tool import FunctionTool
from google.cloud import bigquery

# Environment variables for VCL wrapper and token
WRAPPER_URL = os.environ.get("VCL_WRAPPER_URL", "http://127.0.0.1:8080/mcp")
TOKEN = os.environ["VCL_TOKEN"]

# Tool 1: Governed context, THROUGH the VCL wrapper (gated)
vcl_context = McpToolset(
    name="vcl_context", # Explicitly name for easier tracking in run_result
    connection_params=StreamableHTTPConnectionParams(
        url=WRAPPER_URL,
        headers={"Authorization": f"Bearer {TOKEN}"},
        timeout=10,
        sse_read_timeout=10,
    )
)

# Placeholder for BigQuery tool, will