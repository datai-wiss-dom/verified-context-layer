# L210 Learning Report — Governance at the export boundary (VCL audience-builder)

**Author:** Wissem Khlifi · July 2026
**Course 2 · L210 · model gemini-2.5-flash (Vertex, agentic-2026-493108/us-central1)**

---

## What was built

A single ADK agent, `audience_builder_agent` (an `LlmAgent` in
`vcl_audience_demo/agent.py`), that autonomously builds a marketing "win-back" audience
from a governed customer Data Product — and a runner (`vcl_audience_demo/run_demo.py`)
that sends ONE fixed brief and runs the agent TWICE. The only thing that differs between
the two runs is the Data Product's verification state in Knowledge Catalog:

- **Run A — Data Product VERIFIED:** the VCL wrapper delivers the full governed context;
  the agent authors a PII-safe SQL query (`customer_id`, `customer_segment`,
  `lifetime_value`; **no email**; the sanctioned `customers_safe` JOIN `orders`; 90-day
  filter) and the action tool **executes** it → a real 183-row audience.
- **Run B — Data Product UNVERIFIED:** the wrapper **withholds** the context (honest
  note); the agent builds nothing and explains re-certification is pending; and the
  action tool **refuses** even a sanctioned query purely on the verdict.

The agent is naive about VCL — its instruction contains no verification or PII rule.
Enforcement is entirely structural, in the two tools.

---

## Concepts and Design (WHY each ADK choice)

**`LlmAgent` (one agent, run twice) — not a `SequentialAgent`/router/saga.**
The whole thesis is "same agent, same brief, behavior differs only by catalog state." A
multi-agent workflow would confound that: any behavior difference could be attributed to
routing logic. One `LlmAgent` invoked twice isolates the *single* independent variable
(verification state), which is what makes the demo credible.

**`McpToolset` + `StreamableHTTPConnectionParams` — for governed context (tool 1).**
The customer context must arrive *through* the VCL wrapper (an MCP server on
`127.0.0.1:8080/mcp`), never from Knowledge Catalog directly. `McpToolset` is ADK's
client for a remote MCP server; `StreamableHTTPConnectionParams` (not `Stdio`/`Sse`) is
the right transport because the wrapper is a remote HTTP MCP endpoint with bearer auth.
We set `tool_filter=["lookup_context"]` so the agent has exactly one, unambiguous way to
fetch grounding — reducing the chance it wanders to `search_entries` and drifts off-script.

**`FunctionTool` for the BigQuery action (tool 2) — not the ADK built-in BigQuery toolset.**
The action tool must do something the built-in toolset cannot: read the Data Product's
verdict and *refuse* structurally. A `FunctionTool(func=execute_audience_sql)` lets us own
that logic — the verdict gate, the safe-object scoping, and the PII safety net all live in
one Python function whose behavior we control and can prove.

**`Runner` + `InMemorySessionService` — one-shot invocation.**
The demo is a single fixed brief, so a full session service is unnecessary; an in-memory
session per run is enough. The `Runner.run_async` event stream is also what lets the
runner capture *ground truth* — the actual tool calls and responses — rather than trusting
the agent's prose (see `get_function_calls()` / `get_function_responses()` in `run_demo.py`).

**`BigQueryAgentAnalyticsPlugin` on the `Runner` — observability without an `App`.**
`Runner` accepts `plugins=[...]` directly, so we attach the plugin there (guarded by
`_analytics_plugins()`), avoiding a larger `App` refactor. Every invocation streams a full
trace to `agent_analytics.c2_l210_agent_events`.

---

## Implementation walkthrough (step by step)

1. **Config from env (`agent.py`).** `load_dotenv()` reads the repo-root `.env`; all
   identifiers (`PROJECT`, `DP_RESOURCE`, `LOCATION`, `WRAPPER_URL`) come from the
   environment — no hardcoded project/number in code. `SAFE_VIEW`, `ORDERS_VIEW`, and
   `ALLOWED_OBJECTS` are derived from `PROJECT`.

2. **Reuse the wrapper's verdict reader (`agent.py`).** `read_source_tier` is loaded from
   `src/vcl_wrapper.py` via `importlib.util.spec_from_file_location`. Loading the wrapper's
   *actual* function (rather than re-implementing it) is what makes "the action tool reads
   the SAME `source_tier` the wrapper reads" true by construction.

3. **Tool 1 — `vcl_context = McpToolset(...)`.** Points at `WRAPPER_URL` with an
   `Authorization: Bearer` header. Verified → the wrapper returns the composed context
   (safe view name, JOIN, segment enum, PII rule). Unverified → it returns a text-only
   withhold note.

4. **MCP compatibility shim (`agent.py`).** Google's `lookup_context` advertises an output
   schema, so the strict MCP client (`mcp.client.session.ClientSession._validate_tool_result`)
   rejects the wrapper's text-only withhold response. We wrap that method
   (`_lenient_validate_tool_result`) to accept results whose `structuredContent is None`.
   This is a client-side accommodation — it does not modify the wrapper.

5. **Tool 2 — `execute_audience_sql(sql)` (`agent.py`).** Three structural gates, in order:
   - **Gate 1 (verdict):** `read_source_tier(DP_RESOURCE)`; if not `verified`, return
     `refused_unverified` — whatever SQL was submitted.
   - **Gate 2 (scope):** `_referenced_objects(sql)` parses table refs; anything outside
     `ALLOWED_OBJECTS` (`customers_safe`, `orders`) → `refused_out_of_scope`. This makes
     the PII-bearing `customers` view physically unreachable.
   - **Gate 3 (PII safety net):** refuse any SQL mentioning `email` (defense-in-depth; the
     safe view has no email column anyway).
   - Only then does it run the query via `bigquery.Client` and return rows.

6. **The agent (`audience_builder_agent = LlmAgent(...)`).** Instruction says only: call
   `lookup_context`, build strictly from what it returns, call `execute_audience_sql`, and
   relay plainly if a tool declines. **No** enforcement, no VCL, no PII rule in the prompt.

7. **The runner (`run_demo.py`).** Sends `BRIEF` once; from the event stream it captures
   and prints the raw MCP context (or withhold note), the authored SQL, the executed SQL,
   the final response, and a **structural enforcement probe** that hands
   `SANCTIONED_SAMPLE_SQL` directly to `execute_audience_sql` (identical both runs) to prove
   the tool — not the prompt — is what enforces.

8. **Reproducible cycle.** `src/vcl.py seal` → Run A → edit DP docs + `src/vcl.py enforce`
   (semantic drift → unverified) → Run B → re-seal clean.

---

## Best practices applied

- **Structural over instructional enforcement (Principle 1).** The prompt cannot be the
  thing stopping a PII leak — a prompt is advisory and an LLM can be argued out of it. Both
  tools enforce structurally: tool 1 *withholds*, tool 2 *refuses on the verdict*. Proven by
  the probe: it submits valid SQL in Run B and is still declined.
- **Ground truth over prose.** `run_demo.py` reads `get_function_calls()`/
  `get_function_responses()` from the event stream — the real executed vs refused SQL — not
  the agent's narrative. An agent that "declines" is shown to have declined *because the
  context was withheld*.
- **Single independent variable.** Same agent, brief, and model both runs; only the catalog
  state changes. This is what makes the causal claim honest.
- **Defense in depth for PII.** `customers_safe` excludes email by construction; tool 2 is
  scoped to it; and a third `email`-substring guard exists — three independent layers.
- **Secrets/config hygiene.** `load_dotenv()` + `.env` (git-ignored) + `.env.example`
  (committed placeholders); no real project id/number/email as a literal in any `.py`.
- **Observability that never blocks.** `_analytics_plugins()` swallows plugin init errors so
  analytics failure cannot break agent execution.

---

## Gaps for production readiness

- **Tool-level scoping should become IAM-level scoping.** `execute_audience_sql` uses a
  hardcoded `ALLOWED_OBJECTS` allow-list and its own `bigquery.Client()`. In production the
  tool should run under an **IAM-scoped service account** that can read `customers_safe` and
  `orders` but *cannot* read `customers` or the base Iceberg tables — so scoping is enforced
  by the platform, not by a regex in `_referenced_objects`. The current regex is a
  reasonable demo stand-in but is bypassable (e.g. unusual quoting, CTEs, `INFORMATION_SCHEMA`).
- **The MCP shim is a client-side patch of a wrapper defect.** `_lenient_validate_tool_result`
  monkeypatches `mcp.client.session.ClientSession`. The correct long-term fix is in
  `src/vcl_wrapper.py`: the withhold response should either set `isError: true` (validation
  is skipped for errors) or include a schema-valid `structuredContent`. The shim was used
  only because that file was out of scope to modify.
- **`VCL_TOKEN` is an ephemeral bearer token.** It expires (~1h) and must be re-exported
  before each run. Production should mint tokens from the attached service account
  (workload identity), not `gcloud auth print-access-token`.
- **The LLM-judge gate is mis-calibrated (see below).** `faithfulness` scores a *correct
  safe refusal* as 0. A task-appropriate criterion ("avoided exporting PII / avoided acting
  on withheld context") is needed before the numeric gate is trustworthy.
- **No automated round-trip test.** The reproducible cycle is run by hand. A test that seals,
  runs A, drifts, runs B, and asserts `executed==True` then `refused_unverified` would catch
  regressions (e.g. a future ADK MCP change breaking the shim).
- **Pre-existing lint nit** in `src/vcl_wrapper.py:242` (`build_withhold_note`, f-string with
  no placeholders) — untouched because the wrapper's logic was out of scope.

---

## Evaluation results

From `.claude/current/eval_results.md`:

- **Observability: PASS.** Full traces stream to `agent_analytics.c2_l210_agent_events`
  (LLM requests/responses, both tool calls, invocation lifecycle).
- **LLM-as-Judge (gemini-2.5-flash, faithfulness): unreliable as a gate here.** Three
  sessions captured: `34c4ab65` (verified/built) scored **1.00 / passed**; `e5643a75`
  (verified/built) scored **0.00**; `22f33f74` (unverified/declined) scored **0.00**.
- **Two artifacts, not agent defects:** (1) *non-determinism* — the same verified "built the
  183-audience" response scored 1.00 once and 0.00 another; (2) *mis-calibration* — a correct
  safe decline has no tool output to "ground" on, so faithfulness reads it as 0.
- **Sessions needing review:** `e5643a75` and `22f33f74` show FAIL, but inspection of the
  raw executed/refused SQL confirms both behaved correctly. **Action:** in `/eval`, replace
  the faithfulness gate with a governance-appropriate criterion before trusting the score.
- **Regression: N/A** (first day; no prior-week baseline).

---

## Key learnings (specific to this lesson)

1. **Reuse the enforcing code, don't reimplement it.** Loading `read_source_tier` from
   `src/vcl_wrapper.py` (via `importlib`) makes "tool 2 reads the same verdict as the
   wrapper" true *by construction* rather than by hope. Next lesson: when two components must
   agree on a decision, share the function — divergence is the bug you won't see until prod.
2. **A withholding MCP tool breaks strict clients.** Google's `lookup_context` has an output
   schema, so the MCP client demands `structuredContent`; a text-only "withhold" is rejected
   unless `isError` is true. If you build MCP servers that return "nothing, on purpose," set
   `isError: true` or return schema-valid structured content — otherwise every strict client
   errors on your happy-path refusal.
3. **Capture tool calls from the event stream, never parse the prose.** `event.get_function_calls()`
   and `event.get_function_responses()` are the only trustworthy evidence of what an agent
   *did*. Build this into every runner from now on.
4. **Enforcement in the prompt is not enforcement.** The probe (submit valid SQL → still
   refused) is the proof that matters. Any time you're tempted to write "you MUST NOT…" in an
   instruction, move that rule into a tool that reads state and refuses.
5. **`Runner` takes `plugins=` directly** — you don't need an `App` to attach
   `BigQueryAgentAnalyticsPlugin`. Guard plugin init so observability can never block the
   agent's real work.
