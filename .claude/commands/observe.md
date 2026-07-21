---
name: observe
description: Add BigQuery Agent Analytics observability and LLM-as-Judge to current ADK agent. Invoke after implementing the exercise.
---

# /observe -- Observability and Evaluation Skill

Adds BigQueryAgentAnalyticsPlugin to App() and
sets up LLM-as-Judge evaluation pipeline.

## Quick steps

1. Install dependencies:
```bash
uv add 'google-adk[bigquery-analytics]>=1.24.0'
uv add bigquery-agent-analytics[llm]
```

NOTE: If uv add fails with corporate auth error
(OAuth2 token expired, Corp Airlock, glogin):
STOP. Do not proceed to next step.
Tell developer: 'Run glogin or gcert then confirm.'
Wait for confirmation then retry uv add exactly.
Never skip this step or write alternative scripts.

2. Create dataset (once per GCP project):
```bash
bq mk --dataset --location=US \
  your-project-id:agent_analytics
```

3. Add plugin to App() in agent main file:
```python
from google.adk.apps.app import App
from google.adk.plugins.bigquery_agent_analytics_plugin import (
    BigQueryAgentAnalyticsPlugin
)
# Each lesson writes to its own BigQuery table
# Table is auto-created by plugin on first run
TABLE_ID = 'c2_l210_agent_events'
app = App(
    name=root_agent.name,
    root_agent=root_agent,
    plugins=[BigQueryAgentAnalyticsPlugin(
        project_id='your-project-id',
        dataset_id='agent_analytics',
        table_id='c2_l210_agent_events'
    )]
)
```

4. Verify events stream to BigQuery:
```bash
bq query --use_legacy_sql=false \
  'SELECT event_type, COUNT(*) as count
   FROM agent_analytics.c2_l210_agent_events
   WHERE DATE(timestamp) = CURRENT_DATE()
   GROUP BY event_type
   ORDER BY count DESC'
```

5. Run LLM-as-Judge:
```python
from bigquery_agent_analytics import Client, TraceFilter
from bigquery_agent_analytics.evaluators import LLMAsJudge
client = Client(
    project_id='your-project-id',
    dataset_id='agent_analytics',
    table_id='c2_l210_agent_events'
)
judge = LLMAsJudge(model='gemini-2.5-flash')
traces = client.list_traces(
    filter_criteria=TraceFilter.from_cli_args(
        last='24h',
    )
)
results = judge.evaluate_batch(traces)
df = results.to_dataframe()
print(df)
```

6. Regression check (run in BQ console):
```sql
WITH baseline AS (
  SELECT AVG(CAST(
    JSON_VALUE(attributes, '$.step_count')
  AS INT64)) as avg_steps
  FROM agent_analytics.c2_l210_agent_events
  WHERE event_type = 'INVOCATION_COMPLETED'
  AND DATE(timestamp) BETWEEN
    CURRENT_DATE() - 8 AND CURRENT_DATE() - 1
),
today AS (
  SELECT AVG(CAST(
    JSON_VALUE(attributes, '$.step_count')
  AS INT64)) as avg_steps
  FROM agent_analytics.c2_l210_agent_events
  WHERE event_type = 'INVOCATION_COMPLETED'
  AND DATE(timestamp) = CURRENT_DATE()
)
SELECT
  ROUND(today.avg_steps / baseline.avg_steps, 2)
    as step_ratio,
  CASE
    WHEN today.avg_steps / baseline.avg_steps > 1.3
    THEN 'REGRESSION'
    ELSE 'OK'
  END as status
FROM today, baseline
```

If plugin fails, warn user and continue.
Do not block agent execution for analytics.
