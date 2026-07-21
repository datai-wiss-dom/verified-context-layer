# L210 Exercise Requirements

## Goal

Build an ADK agent to autonomously build a marketing "win-back" audience from a governed Data Product via a VCL wrapper, demonstrating behavior changes based on the Data Product's verification state using the same agent and brief.

## Deliverables

- [ ] A single ADK `LlmAgent` named "audience_builder_agent"
- [ ] The `audience_builder_agent` includes a tool for **governed context** using `McpToolset` and `StreamableHTTPConnectionParams` to connect to the VCL wrapper's MCP endpoint.
- [ ] The `audience_builder_agent` includes a **BigQuery action tool** for authoring and executing audience queries.
- [ ] A runner script that sends one fixed brief to the agent.
- [ ] The runner prints the agent's final response.
- [ ] The runner prints the raw MCP context received by the agent (or the withhold note).
- [ ] The runner prints the SQL authored by the agent.
- [ ] The runner prints the executed SQL (for the verified path).
- [ ] The fixed brief: "Build the win-back campaign audience: high-value customers who have not ordered in the last 90 days. Produce an audience export the marketing platform can use to reach them."
- [ ] Implementation for Run A: Data Product **VERIFIED** state.
- [ ] Implementation for Run B: Data Product **UNVERIFIED** state.

## Acceptance criteria

- The agent connects to the wrapper (not KC directly) and, in Run A, retrieves the governed customer context.
- Run A: the agent authors a query that **EXCLUDES email**, uses the sanctioned JOIN and segment values, applies the 90-day filter, and executes it to produce an audience.
- Run B: SAME agent, SAME brief -> the BigQuery TOOL refuses to execute (it reads the unverified verdict), so no audience is built. The agent then explains re-cert is pending. Enforcement is in the TOOL, not the instruction.
- Prove enforcement is structural: even if the agent submits SQL in Run B, the tool declines because the DP is unverified — not because the instruction told the agent to stop. (The agent instruction contains no enforcement.)
- The ONLY difference between runs is the catalog verification state — not the brief, not the agent code, not the model.
- Reproducible: seal -> Run A -> drift+enforce -> Run B -> re-seal clean.

## Out of scope

- No second agent, no router, no saga — one agent, run twice.
- No changes to `vcl.py` / `vcl_wrapper.py` / `vcl_triage.py`.
- No new IAM design work, no deploy — local, wrapper on 127.0.0.1:8080.
- Do NOT make the agent "aware" of VCL or instruct it to check verification — the gating works purely through what the wrapper returns or withholds.