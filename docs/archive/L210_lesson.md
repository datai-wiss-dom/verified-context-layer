# L9 — Prompt Chaining: Key Concepts

## What prompt chaining is in ADK
Sequential workflow where output of one agent step feeds
as input to the next. ADK implements this via SequentialAgent.

## Core ADK classes for this lesson
- `SequentialAgent` — runs sub_agents in order, passes state
- `LlmAgent` — each step in the chain
- `InvocationContext` — carries state between steps
