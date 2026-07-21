---
name: report
description: Generate learning report and save to .claude/current/report.md. Invoke after /observe and /eval have passed.
---

The exercise is complete. Now generate a learning report and save it to .claude/current/report.md with these sections:

## What was built

## Concepts and Design
Explain WHY each ADK concept was chosen, not just what it is.

## Implementation walkthrough
How it works step by step. Reference actual file names and class names from the code.

## Best practices applied
What was done well and why it matters in production.

## Gaps for production readiness
What is missing, why it matters, how to fix it.
Be specific -- reference actual files and functions.

## Evaluation results
If .claude/current/eval_results.md exists, summarize
the key scores and any sessions that need review.
If it does not exist, write: Run /eval to generate results.

## Key learnings
3-5 bullet points specific to THIS implementation.
Each must be something a learner would not know before this lesson. Make them actionable for the next lesson.

Be educational -- explain WHY every decision was made, not just WHAT was built. Reference specific files and classes.
