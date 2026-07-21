# Concept — Governance at the export boundary: verified grounding for an agentic action
**Author:** Wissem Khlifi ·

**July 2026**

## The idea in one sentence
When an agent takes an autonomous action that moves data OUT of your governance
boundary, the last thing standing between "safe" and "a PII leak" is whether the
context it grounded on is still certified — VCL makes that a structural gate the agent
cannot bypass.


## The scenario
A campaign audience-building agent is asked to build a marketing audience ("high-value
customers who have lapsed"). To do this it must consume the customer Data Product, join
customers to orders, filter, and produce an audience EXPORT for an external marketing
platform. The moment of danger is the export: once customer email lands in an external
marketing tool it has left your governance boundary and cannot be recalled. Exporting
raw PII to an external system is one of the most common, most serious real-world
data-governance incidents.


## Why this is agentic, not QA
This agent does not answer a question — it takes a consequential action: it authors and
executes a data operation that produces a persistent artifact (an audience export). It
reasons about which attributes to use, applies a business definition, uses a sanctioned
JOIN, and acts. That is agency, and it is exactly the surface a real Data Engineering
Agent operates on. (A QA/RAG answer over a description field is not — we have SQL and
databases for that.)


## Where governance lives
The customer Data Product carries the rules: "email is PII — never expose", the allowed
customer_segment values, the sanctioned JOIN pattern to orders, lifetime_value is
pre-calculated. A correctly grounded agent inherits these and builds a PII-safe
audience. An agent grounded on drifted-but-uncertified context, or no context, would
build an export that leaks — baking customer email into an artifact that propagates
everywhere downstream.


## What VCL does here
VCL is the gate at the grounding step. The agent gets its customer context THROUGH the
VCL wrapper (an MCP server between the agent and Knowledge Catalog), never from KC
directly:
- context VERIFIED -> wrapper delivers the full governed context -> agent builds a
  PII-safe audience and executes it.
- context UNVERIFIED (rules drifted, not re-certified) -> wrapper WITHHOLDS the context
  with an honest note -> agent has no governance to act on -> it does NOT build the
  export.


## The principle: structural, not instructional
The agent is NOT told "check if the data is verified" or "don't leak PII". It is only
told: get the customer context from your tool, build strictly from what you receive,
and if the tool gives you no usable governance, do not build the export. The wrapper
enforces by WITHHOLDING — the agent physically cannot ground on context it never
receives. Governance is a property of the platform the agent sits on, not a rule the
agent must be trusted to follow. (Principle 1: structural over instructional.)


## The transitive-governance insight (the L7 point)
Verification is not just about one Data Product's answers. It is about the data SUPPLY
CHAIN: any new artifact an agent builds FROM a source must inherit the source's
governance — or not be built at all. VCL makes verification hold at the exact moment
data would cross the boundary into a system you no longer govern. After that moment it
is too late.


## The honest demo
ONE agent, ONE brief, run TWICE. The only variable is the catalog verification state.
Verified -> governed audience built and executed. Unverified -> export declined. The
agent is identical and naive about VCL, so the behaviour difference can only come from
the grounding the wrapper controls. That is what makes it credible.
