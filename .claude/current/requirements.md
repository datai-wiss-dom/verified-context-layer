# Requirements — Campaign Audience-Building Agent (VCL demo)
**Author:** Wissem Khlifi ·


**July 2026**


## Business requirements


**BR-1 — The business need.** The marketing team wants to run a "win-back" campaign
targeting high-value customers who have lapsed (no recent orders). They ask a data
agent to build the target audience automatically.


**BR-2 — The agent's job.** Given a plain-language campaign brief, the agent
autonomously builds the audience: it must identify the right customers, apply the
business definition of "high-value" and "lapsed", and produce an audience export the
marketing platform can consume.


**BR-3 — Why the agent needs the customer Data Product.** The agent cannot build a
customer audience without customer data. It must consume the governed
`ecommerce-customer-intelligence` Data Product to know: which attributes exist
(lifetime_value, customer_segment), the allowed segment values, the sanctioned JOIN
pattern to orders, and the governance rules — critically, that **email is PII and must
never be exposed** in an export that leaves the platform.


**BR-4 — The governance stake (why this matters).** The audience export LEAVES the
company's governance boundary — it goes to an external marketing platform. Once
customer email crosses that boundary it cannot be recalled. Exporting raw customer
email to an external marketing tool is a real, common, serious data-governance
incident (PII exfiltration). The agent must produce an audience that is useful for
targeting WITHOUT exposing PII.


**BR-5 — The verification requirement.** The agent may only build the audience while
the customer Data Product's context is currently verified. If the governance context
has drifted (e.g. the PII rule was edited and not re-certified), the agent must NOT
proceed to build/export the audience — because it would be acting on governance that no
human currently vouches for. A confidently-ungoverned export is worse than no export.


**BR-6 — The demonstration.** The same agent, given the same brief, must behave
correctly in two states: (A) context verified → builds a governed, PII-safe audience;
(B) context unverified → declines to build the export and explains that customer
governance is pending re-certification. The ONLY variable is the catalog verification
state.


## Technical requirements


**TR-1 — Agent framework.** ADK `LlmAgent`, model gemini-2.5-flash, Vertex backend
(project agentic-2026-493108, us-central1).


**TR-2 — Two tool sources (the key architecture):**
- **Governed context** via the **VCL wrapper** (McpToolset +
  StreamableHTTPConnectionParams -> http://127.0.0.1:8080/mcp, bearer auth). How the
  agent learns the customer DP's governance: which SAFE view to query
  (`ecommerce_views.customers_safe`), the sanctioned JOIN to `ecommerce_views.orders`,
  the segment values, and that email is PII. VCL gates this: verified -> full context
  (incl. the safe view name); unverified -> withheld + honest note.
- **Action tool** to author/execute BigQuery. STRUCTURALLY SCOPED (option B-light): the
  tool only executes against the view name(s) HANDED TO IT BY THE CONTEXT — it will not
  query arbitrary tables. Since verified context hands only `customers_safe` (which has
  no email), the agent physically cannot select email through this tool. If context is
  withheld (unverified), the tool is handed no target and executes nothing.


**TR-2a — The structural chain (why this proves VCL, not just column security):**
Verification -> context delivery -> the query target. The safe view `customers_safe`
excludes email by construction (PII safety). But WHICH view the agent may use is
delivered ONLY by verified context. Withhold the context (unverified) and the agent has
no target to act on. So the VERIFICATION STATE structurally determines whether the agent
can act at all — that is what makes it a VCL demo and not merely a static column-security
demo. The agent still authors free-form SQL against the handed safe view (real agency),
but the surface it can reach contains no PII and is gated by verification.


**TR-3 — The autonomous action (author-and-execute, safe path only).**
- On VERIFIED context: the agent authors a governed SQL query against
  `ecommerce_views.customers_safe` JOIN `ecommerce_views.orders` (the sanctioned
  pattern), filters (high lifetime_value AND no orders in 90 days), selects a non-PII
  audience (customer_id, segment, lifetime_value; NO email — email is not in the safe
  view), and EXECUTES it to materialize the audience. Real action, real result, no PII.
- On UNVERIFIED context: the agent receives the withhold note, is handed no view/target,
  does NOT author or execute any export, and explains re-certification is pending. The
  "what it would have leaked without governance" is shown by CONTRAST/discussion, NOT by
  executing a PII-exposing query.


**TR-3a — Real objects (verified live 2026-07-20):**
- Safe view: `agentic-2026-493108.ecommerce_views.customers_safe` — columns
  [customer_id, country, city, signup_date, customer_segment, lifetime_value]; NO email/
  first_name/last_name (confirmed by schema read).
- Unsafe (locked out): `ecommerce_views.customers` (HAS email) + base Iceberg tables.
- Join target: `ecommerce_views.orders` (view).
- Production hardening (documented seam): replace tool-level scoping with an IAM-scoped
  service account that can read customers_safe/orders but NOT customers or base tables.


**TR-4 — Enforcement is in the TOOLS, not the agent instruction (Principle 1, both sides).**
Neither tool trusts the agent to self-police. Enforcement is structural in BOTH tools:
- Tool 1 (context, via wrapper): withholds unverified context.
- Tool 2 (BigQuery action): reads the DP's verdict (the same source_tier the wrapper
  reads) and REFUSES to execute against an unverified DP's data, regardless of what SQL
  the agent submits. The agent cannot make Tool 2 act on unverified data by any prompt.
  The agent instruction must NOT contain enforcement ("you MUST NOT query if withheld").
  It only: (a) tells the agent to get context and build strictly from it, and (b) as
  EXPLANATION-ONLY, tells the agent how to inform the user when a tool declines. If the
  instruction were the thing stopping the leak, that would be instructional enforcement —
  the exact Principle-1 failure. The tools stop it; the instruction only explains.


**TR-5 — Round-trip verification.** Confirm behaviour by inspecting the RAW tool result
(what context the wrapper delivered or withheld) and the ACTUAL authored/executed
query — not the agent's prose. An agent that "declines" must be shown to have declined
because the context was withheld, not for an unrelated reason.


**TR-6 — Reproducibility.** seal -> Run A -> drift+enforce -> Run B -> re-seal clean.
No changes to vcl.py / vcl_wrapper.py / vcl_triage.py. Local only (wrapper on
127.0.0.1:8080), no deploy.


**TR-7 — Safety.** Never execute a query that selects email into an export during the
demo. The verified path is PII-safe by construction; the unverified path executes
nothing. The danger is demonstrated by contrast, never by a real leak.


## Scope guards
- ONE agent, run twice. No router, no second agent, no saga.
- The agent has exactly two tools: VCL-wrapped context (read) + BigQuery action.
- Governance is inherited through the gated context, enforced structurally by the
  wrapper withholding — never by instructing the agent to self-police.


