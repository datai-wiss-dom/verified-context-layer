# L210 — Governance at the export boundary (VCL audience-builder demo)

**Author:** Wissem Khlifi · July 2026

ONE ADK agent, ONE brief, run TWICE. The only variable between runs is the customer Data
Product's verification state in Knowledge Catalog. Verified → a governed, PII-safe
audience is built and executed. Unverified → the export is declined. The agent is
identical and naive about VCL; the behaviour difference comes only from what the wrapper
delivers/withholds and what the action tool's verdict-gate allows.

## Files

| File | What it is |
|---|---|
| `agent.py` | The single `LlmAgent` `audience_builder_agent` with its two tools. |
| `run_demo.py` | The runner: sends the fixed brief once and prints everything from the raw event stream. |

### The two tools (enforcement is STRUCTURAL, in the tools — not the prompt)

1. **`vcl_context`** — governed context THROUGH the VCL wrapper (`McpToolset` +
   `StreamableHTTPConnectionParams` → `http://127.0.0.1:8080/mcp`, bearer auth), filtered
   to `lookup_context`. Verified → the wrapper delivers the full customer context
   (safe view name, orders JOIN, segment enum, PII rule). Unverified → the wrapper
   **withholds** the whole context and returns an honest note.
2. **`execute_audience_sql`** — the BigQuery action tool. It **reads the DP's verdict
   itself** (`read_source_tier`, imported from `vcl_wrapper` — literally the same code the
   wrapper reads) and **refuses to execute against an unverified DP, whatever SQL is
   submitted**. It is also structurally scoped to the sanctioned safe objects
   (`ecommerce_views.customers_safe` + `ecommerce_views.orders`), so it can never touch
   the PII-bearing `customers` view or select `email`.

The agent instruction contains **no** enforcement, no mention of VCL, verification, or
PII. It only says: get the context, build strictly from it, and relay plainly if a tool
declines.

> **MCP compatibility shim (agent.py):** Google's `lookup_context` advertises an output
> schema, so the strict MCP client would reject the wrapper's text-only *withhold*
> response. `agent.py` relaxes client-side validation for text-only results so the honest
> withhold note reaches the agent. This is a client accommodation — it does **not** modify
> `vcl_wrapper.py` / `vcl.py` / `vcl_triage.py`.

## Prerequisites

```bash
# From the repo root. Vertex ADC + the objects/aspects from TR-3a already exist.
gcloud config set project agentic-2026-493108
gcloud auth application-default login          # ADC for BigQuery + Vertex
export VCL_TOKEN=$(gcloud auth print-access-token)   # bearer for the wrapper
```

The demo reads the DP verdict + safe views live; it needs the `customers_safe` and
`orders` views and the DP's overview/queries to reference them (see the repo's
`docs/reference/` for how the DP was set up).

## Reproducible sequence: seal → Run A → drift+enforce → Run B → re-seal clean

Common args (used by every `vcl.py` call):

```bash
DP_ENTRY="projects/129682754245/locations/us-central1/dataProducts/ecommerce-customer-intelligence"
DP_RES="projects/129682754245/locations/us-central1/entryGroups/@dataplex/entries/${DP_ENTRY}"
ASPECT="projects/129682754245/locations/us-central1/aspectTypes/verification"
COMMON="--project agentic-2026-493108 --project-number 129682754245 --location us-central1 \
  --entry-group @dataplex --dp-entry ${DP_ENTRY} --dp-resource ${DP_RES} \
  --aspect-type ${ASPECT} --quality-scan customers=customers--quality:24"
```

**1. Seal (certify current state → verified):**
```bash
python3 src/vcl.py seal $COMMON
```

**2. Start the wrapper (leave running in its own shell):**
```bash
export VCL_TOKEN=$(gcloud auth print-access-token)
python3 src/vcl_wrapper.py            # serves http://127.0.0.1:8080/mcp
```

**3. Run A — VERIFIED:**
```bash
export VCL_TOKEN=$(gcloud auth print-access-token)
python3 vcl_audience_demo/run_demo.py
```
Expected: raw context is the full governed context; the agent authors a PII-safe query
(`customer_id`, `customer_segment`, `lifetime_value`; **no email**; `customers_safe` JOIN
`orders`; 90-day filter) and the action tool **executes** it → audience built. The
structural probe also executes (verified).

**4. Drift + enforce (→ unverified):** edit the DP's `documentation`/overview in the KC
UI (any rule text change), then:
```bash
python3 src/vcl.py enforce $COMMON
# -> VERDICT: UNVERIFIED (semantic drifted); source_tier written 'unverified'
```

**5. Run B — UNVERIFIED (same agent, same brief, change nothing else):**
```bash
python3 vcl_audience_demo/run_demo.py
```
Expected: raw context is the **withhold note** (semantic drifted, re-cert pending); the
agent authors/executes nothing and explains re-certification is pending; the structural
probe shows the action tool **refuses** the sanctioned query purely on the verdict
(`refused_unverified`) — proving enforcement is in the tool, not the instruction.

**6. Re-seal clean (restore verified):** revert the doc edit, then:
```bash
python3 src/vcl.py seal $COMMON
```

## What each acceptance criterion maps to

- Connects to the wrapper (not KC) and retrieves governed context in Run A → tool 1.
- Run A excludes email, uses the sanctioned JOIN + segment values + 90-day filter, and
  executes → section 2/3 of the runner output.
- Run B: the action TOOL refuses (reads the unverified verdict); no audience built →
  section 5 probe (`refused_unverified`).
- Enforcement is structural, not instructional: the probe submits valid SQL and is still
  declined on the verdict alone; the agent instruction contains no enforcement.
- Only the catalog verification state differs between runs — same brief, agent, model.
- Reproducible via the sequence above.

## Safety

The verified path is PII-safe by construction (`customers_safe` has no email; the action
tool is scoped to it and rejects any `email` reference). The unverified path executes
nothing. The leak risk is shown by contrast, never by a real leak.
