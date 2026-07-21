# L210 - Governance at the export boundary: verified grounding for an agentic action: Key Concepts

## What verified grounding at the export boundary is in ADK

**Verified Grounding** at the **export boundary** is a mechanism within ADK, facilitated by the **Verified Context Layer (VCL)**, to structurally enforce governance for agentic actions. It ensures that autonomous agents only perform consequential actions, like data exports, when grounded on certified and up-to-date context. This prevents data governance incidents, such as PII leaks, by withholding context if it's unverified.

## Core ADK classes for this lesson

- `VCL wrapper` - intercepts agent requests for context, delivering only verified information.
- `MCP server` - hosts the `VCL wrapper`, acting as an intermediary between agents and the `Knowledge Catalog`.
- `Knowledge Catalog` - provides the raw data product context, which is then filtered/verified by the `VCL wrapper`.

## Key decisions for my implementation

- **Structural Governance**: Implement the **Verified Context Layer (VCL)** as an `MCP server` acting as a `VCL wrapper` between the agent and the `Knowledge Catalog`. This ensures agents can only ground on verified context, preventing actions based on uncertified or drifted data.
- **Export Boundary Protection**: Use the `VCL` to gate agent actions that move data out of the governance boundary (e.g., data exports). If context is unverified, the `VCL wrapper` withholds it, structurally preventing the agent from performing the export.
- **Transitive Governance**: Design the system such that any new artifact an agent builds from a source must inherit the source's verified governance, or the action is blocked, especially at critical export points.

## Gaps / questions from lesson

- How is context "verified" or "re-certified" within the `Knowledge Catalog` or by the `VCL`? What are the triggers for a context becoming "unverified"?
- What specific `MCP` capabilities are utilized to implement the `VCL wrapper`'s interception and withholding logic?