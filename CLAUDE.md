# Agentic Workflows ADK — Project Context

## Identity
- Profile :Agentic AI Engineer
- GitHub: datai-wiss-dom
- GCP Project: your-project-id (real value in .env, key VCL_PROJECT)
- GCP Account: your-account@example.com


## Active Context (read these for current work)
@.claude/current/plan.md

## Handoff from Antigravity
If HANDOFF.md exists at project root, read it first.
It contains completed steps, remaining steps, file states,
and the exact next action to continue from.

## Optional Extension
data-agent-kit-starter-pack may be installed on this machine.
If available, use its GCP data engineering skills for
BigQuery, Spanner, Dataproc, dbt, and Spark tasks.
If not available, continue normally without it.

## Stack
- Language: Python 3.13 | Package manager: uv
- Framework: Google ADK
- IDE: IntelliJ IDEA 2025.3
- AI tools: Claude Code CLI, Gemini CLI, Antigravity, agents-cli
- Deployment: Cloud Run / Vertex AI Agent Engine

## Critical Rules
- Always use `uv add` not `pip install`
- New ADK projects: `agents-cli create <name> --adk --yes`
- Scaffold syntax: `agents-cli scaffold create <name>` (not scaffold <name>)
- Never commit .env or service account keys
- ADC auth: `gcloud auth application-default login`

## Lesson Advancement Protocol
When moving to next lesson:
1. mv .claude/current/* docs/archive/
2. Write fresh .claude/current/ files for new lesson
3. Update 'Current Position' section above

## Available Skills (invoke on demand)
- /deploy    → deploy agent to Cloud Run
- /eval      → local eval + BigQuery LLM-as-Judge
- /scaffold  → create new ADK agent scaffold
- /review    → review agent code against ADK patterns
- /observe   → add BigQuery observability + LLM-as-Judge
- /report   -> generate learning report to .claude/current/report.md
- /security -> run pre-commit security audit

## Observability Protocol
Every agent MUST include BigQueryAgentAnalyticsPlugin.
Invoke /observe after implementing each exercise.
Invoke /eval to run full evaluation before submission.

## What NOT to auto-load
- docs/archive/ — previous lessons (cold storage, never auto-read)
- docs/reference/ — load only when explicitly needed
