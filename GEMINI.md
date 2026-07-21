# Gemini CLI Context — Agentic Workflows ADK

## Role
You are my Google-native AI assistant for GCP and ADK questions.
Use this when Claude Code quota runs out or for GCP-native queries.

## Project
- GCP Project: your-project-id
- Region: us-central1
- Auth: ADC (gcloud auth application-default login)

## Current Work
See .claude/current/lesson.md for active lesson context.
See .claude/current/exercise.md for what we are building.

## Preferred Patterns
- ADK agents via agents-cli, not manual boilerplate
- Vertex AI Gemini models (gemini-2.5-flash default)
- uv for Python packaging
- Cloud Run for deployment unless told otherwise

## Handoff from Antigravity
If HANDOFF.md exists at project root, read it first.
It contains completed steps, remaining steps, file states,
and the exact next action to continue from.

## Optional Extension
data-agent-kit-starter-pack may be installed on this machine.
Use its GCP data engineering skills automatically when
relevant – BigQuery, Spanner, Dataproc, dbt, Spark,
Dataform, Cloud Composer, notebooks.
If extension fails or is unavailable, continue normally.
