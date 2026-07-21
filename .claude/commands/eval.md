---
name: eval
description: Run full evaluation pipeline -- agents-cli eval
for local tests then BigQuery LLM-as-Judge on lesson-specific
trace table. Run every lesson before submission.
---

# /eval -- Full Evaluation Pipeline

## Stage 1: Local eval
```bash
agents-cli eval run
```
Fix all failures before Stage 2.

## Stage 2: BigQuery LLM-as-Judge
```python
from bigquery_agent_analytics import Client, TraceFilter
from bigquery_agent_analytics.evaluators import LLMAsJudge
import datetime

# Each lesson has its own table
LESSON_LABEL = 'c2_l210'
TABLE_ID = 'c2_l210_agent_events'

client = Client(
    project_id='your-project-id',
    dataset_id='agent_analytics',
    table_id=TABLE_ID,
)
judge = LLMAsJudge(model='gemini-2.5-flash')
traces = client.list_traces(
    filter_criteria=TraceFilter.from_cli_args(last='24h')
)
results = judge.evaluate_batch(traces)
df = results.to_dataframe()
print(df)

# Save results
with open('.claude/current/eval_results.md', 'w') as f:
    f.write('# Evaluation Results\n\n')
    f.write(f'**Lesson:** {LESSON_LABEL}\n')
    f.write(f'**Table:** {TABLE_ID}\n')
    f.write(f'**Generated:** {datetime.datetime.now()}\n\n')
    f.write('## Scores\n\n')
    f.write(df.to_markdown(index=False))
print('Saved to .claude/current/eval_results.md')
```

## Stage 3: Regression check SQL
Run in BigQuery console:
```sql
WITH baseline AS (
  SELECT AVG(CAST(
    JSON_VALUE(attributes, '$.step_count') AS INT64
  )) as avg_steps
  FROM agent_analytics.c2_l210_agent_events
  WHERE event_type = 'INVOCATION_COMPLETED'
  AND DATE(timestamp) BETWEEN
    CURRENT_DATE() - 8 AND CURRENT_DATE() - 1
),
today AS (
  SELECT AVG(CAST(
    JSON_VALUE(attributes, '$.step_count') AS INT64
  )) as avg_steps
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

## Submission checklist
- [ ] Stage 1: agents-cli eval run passing
- [ ] Stage 2: LLMAsJudge no hallucination < 3
- [ ] Stage 3: Regression status = OK

NOTE: LESSON_LABEL and TABLE_ID above are baked in
by setup_context_structure.py at generation time.
When script runs for new lesson they update automatically.
