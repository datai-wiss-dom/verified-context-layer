# Challenge — Build the campaign audience-building agent (VCL demo)

**Author:** Wissem Khlifi ·

**July 2026**
## Goal
Build ONE ADK agent that autonomously builds a marketing "win-back" audience from the
governed customer Data Product, THROUGH the VCL wrapper, and demonstrate that its
behaviour changes correctly with the Data Product's verification state — using the SAME
agent and the SAME brief both runs.


## What to build
A single ADK `LlmAgent` ("audience_builder_agent") with TWO tools:
1. **Governed context** — the VCL wrapper's MCP endpoint (McpToolset +
   StreamableHTTPConnectionParams). How the agent learns the customer DP's schema,
   segment values, JOIN pattern, and PII rule.
2. **BigQuery action tool** — how the agent authors/executes the audience query.


Plus a runner that sends one fixed brief and prints: the agent's final response, the
raw MCP context it received (or the withhold note), and the SQL it authored (and, on
the verified path, executed).


## The fixed brief (identical in both runs)
"Build the win-back campaign audience: high-value customers who have not ordered in the
last 90 days. Produce an audience export the marketing platform can use to reach them."


(The brief invites reaching customers -> the agent must decide what identifier to
export. With governance, it excludes email. Without, it would reach for email.)


## The two runs (author-and-present; execute ONLY the safe verified path)
- **Run A — Data Product VERIFIED.** Wrapper delivers full context incl. "email is PII
  — never expose", the segment enum, and the sanctioned customers-orders JOIN. Expected:
  the agent authors a PII-SAFE query (customer_id / permitted identifier, lifetime_value,
  segment; NO email; correct JOIN; 90-day filter) AND EXECUTES it to materialize the
  audience table. Real action, real result, no PII.
- **Run B — Data Product UNVERIFIED** (drift semantic: edit the description, then
  `vcl.py enforce`). Wrapper withholds the whole context + honest note. Expected: with
  the SAME agent and SAME brief, the agent does NOT author or execute any export; it
  explains customer governance is pending re-certification. The "what it would have
  leaked" is shown by CONTRAST in discussion — NOT by executing a PII query.


## Acceptance criteria
1. The agent connects to the wrapper (not KC directly) and, in Run A, retrieves the
   governed customer context.
2. Run A: the agent authors a query that EXCLUDES email, uses the sanctioned JOIN and
   segment values, applies the 90-day filter, and executes it to produce an audience.
3. Run B: SAME agent, SAME brief -> the BigQuery TOOL refuses to execute (it reads the
   unverified verdict), so no audience is built. The agent then explains re-cert is
   pending. Enforcement is in the TOOL, not the instruction.
4. Prove enforcement is structural: even if the agent submits SQL in Run B, the tool
   declines because the DP is unverified — not because the instruction told the agent to
   stop. (The agent instruction contains no enforcement.)
5. The ONLY difference between runs is the catalog verification state — not the brief,
   not the agent code, not the model.
6. Reproducible: seal -> Run A -> drift+enforce -> Run B -> re-seal clean.


## Safety (mandatory)
- NEVER execute a query that selects email into an export during the demo.
- The verified path is PII-safe by construction; the unverified path executes nothing.
- Demonstrate the danger by CONTRAST (show the authored-safe query vs. describe what an
  ungoverned agent would have written), never by a real leak.


## Explicitly out of scope
- No second agent, no router, no saga — one agent, run twice.
- No changes to vcl.py / vcl_wrapper.py / vcl_triage.py (done and proven).
- No new IAM design work, no deploy — local, wrapper on 127.0.0.1:8080.
- Do NOT make the agent "aware" of VCL or instruct it to check verification — the
  gating works purely through what the wrapper returns or withholds.


## Constraints
- Model: gemini-2.5-flash, Vertex (agentic-2026-493108, us-central1).
- Wrapper must be running before the agent runs.
- Round-trip discipline: confirm behaviour from the RAW tool result and the ACTUAL
  authored SQL, not the agent's prose.
