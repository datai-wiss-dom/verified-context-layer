# Agentic Workflows with Google ADK


**Udacity — Google Agentic AI Engineer Nanodegree · Course 2**

**Author:** Wissem Khlifi · 

**GitHub:** [@datai-wiss-dom](https://github.com/datai-wiss-dom) · 

**April 2026**


-----


## What this project is


Coursework for building agentic workflows with [Google ADK](https://google.github.io/adk-docs/) and Vertex AI Gemini.
Beyond the lessons themselves, this repo contains a **context engineering system** — a set of structured files and scripts that keep multiple AI coding tools (Claude Code, Gemini CLI, Antigravity) synchronized and oriented across 56 lessons without re-explaining context every session.


> **Note:** Each Udacity lesson provides its own starter code with a different project structure. Every lesson is a separate IntelliJ project and GitHub repository. The `manageskills/` scripts are copied into each new lesson project.


-----


## The problem it solves


Raw Udacity lesson notes were accumulating as loose `.md` files in the project root. Every AI tool session loaded all of them — wasting tokens, losing focus, and requiring manual re-explanation of project context each time.


|Before                                 |After                                 |
|---------------------------------------|--------------------------------------|
|~50–100k tokens auto-loaded per session|~500 tokens hot + ~2–3k warm on demand|
|Context reset on every new session     |Tools arrive already oriented         |
|Work lost when Antigravity hit quota   |Seamless handoff via `HANDOFF.md`     |


-----


## Architecture — 6 layers


### Layer 1 — Tiered context system


Three tiers control what gets loaded and when:


```
HOT   (~500 tokens) — auto-read every session
     CLAUDE.md       Claude Code CLI
     GEMINI.md       Gemini CLI
     AGENTS.md       Antigravity, Cursor, any tool


WARM  (~2–3k tokens) — current lesson only, slides forward
     .claude/current/lesson.md      <- before coding
     .claude/current/exercise.md    <- before coding
     .claude/current/plan.md        <- before coding
     .claude/current/eval_results.md <- after /eval
     .claude/current/report.md      <- after /report


COLD  (never auto-loaded)
     docs/archive/     previous lessons
     docs/reference/   stable reference, loaded on demand
```


### Layer 2 — Per-tool context files


Each AI tool gets its own instruction file at the project root.
No manual re-explanation — the tool reads its file and knows the stack, rules, and current position.


|File       |Tool                                  |
|-----------|--------------------------------------|
|`CLAUDE.md`|Claude Code CLI                       |
|`GEMINI.md`|Gemini CLI                            |
|`AGENTS.md`|Antigravity · Claude Code · Gemini CLI|


### Layer 3 — Skills system


Stable command patterns, encoded once, invoked on demand. Zero token cost when not in use.


```
.claude/commands/deploy.md    →  /deploy
.claude/commands/eval.md      →  /eval (local + BQ judge)
.claude/commands/scaffold.md  →  /scaffold
.claude/commands/review.md    →  /review
.claude/commands/observe.md   →  /observe
.claude/commands/report.md    →  /report
.claude/commands/security.md  →  /security
```


### Layer 4 — Antigravity handoff protocol


Solves the quota interruption problem. When Antigravity runs out of quota mid-task:


```
.agent/rules/handoff-rule.md   always-on rule — forces HANDOFF.md write on every stop
.agent/workflows/handoff.md    /handoff slash command — trigger manually anytime
AGENTS.md                      cross-tool rule — tells all tools to read HANDOFF.md at start
```


**The flow:**


```
Antigravity hits quota
 → writes HANDOFF.md automatically (forced by rule)
 → Claude Code or Gemini CLI starts
 → reads AGENTS.md → checks HANDOFF.md first
 → continues exactly where Antigravity stopped
```


### Layer 5 — Automation scripts


**`manageskills/setup_context_structure.py`** — run once per new project:


- Creates the full folder structure
- Writes all context files with correct encoding
- Archives existing lesson notes
- Updates `.gitignore`


**`manageskills/ai_md_converter.py`** — run 3× per lesson (lesson, exercise, plan):


- Accepts raw text pasted from Udacity
- Calls Vertex AI Gemini via ADC (no API key needed)
- Outputs compressed markdown in the correct format
- Saves directly to `.claude/current/`
- Auto-archives previous lesson files to `docs/archive/`
- Auto-updates lesson number in `CLAUDE.md`, `GEMINI.md`, and `course-map.md`
- Auto-deletes stale `HANDOFF.md`


### Layer 7 — Observability and Evaluation Stack

Every agent runs with BigQuery Agent Analytics plugin
enabled. Each lesson writes to its own table in the
shared dataset, powering three capabilities:

```
TRACE DATABASE (BigQuery: agent_analytics.{lesson}_agent_events)
    One table per lesson, auto-created on first agent run
    e.g. c2_l9_agent_events, c2_l10_agent_events, c3_l1_agent_events
          |
          ├── Trace Visualization (/observe Layer 2)
          |   Visual DAG of exactly what agent did
          |   Use when debugging unexpected behavior
          |
          ├── LLM-as-Judge (/observe Layer 3 + /eval)
          |   Quality evaluation on real production data
          |   Criteria: task_completion, hallucination,
          |   tool_correctness, step_efficiency
          |
          └── Regression Detection (/observe Step 7 SQL)
              Catches if agent gets worse between lessons
              Blocks submission if regressions detected
```

Invoke with these slash commands in Claude Code:
- `/observe`  → add BigQuery plugin + LLM-as-Judge
- `/eval`     → local eval + BQ judge + regression check
- `/report`   → generate learning report from code
- `/security` → pre-commit security audit

### Layer 6 — Git strategy


```
Committed to GitHub                   Purpose
─────────────────────────────────────────────────────
CLAUDE.md, GEMINI.md, AGENTS.md       team / tool context
.claude/commands/                      skills
.agent/rules/, .agent/workflows/       Antigravity config
docs/reference/                        stable reference
docs/archive/                          lesson history
manageskills/                          scripts


Excluded via .gitignore               Reason
─────────────────────────────────────────────────────
.claude/current/                       ephemeral, personal
.env                                   secrets
HANDOFF.md                             ephemeral, session only
```


-----


## Per-lesson workflow


Each Udacity lesson has its own starter code, its own file structure, and its own GitHub repo.
The `manageskills/` folder is copied into each new lesson project.


### Starting a new lesson project


```bash
# 1. Download Udacity starter code for the lesson
# 2. Open in IntelliJ as new project
# 3. Copy only 2 scripts (everything else auto-generated)
mkdir manageskills
cp /path/to/previous/manageskills/setup_context_structure.py manageskills/
cp /path/to/previous/manageskills/ai_md_converter.py manageskills/
cp /path/to/previous/README.md .
# OPS.md and SKILL_README.md are auto-generated by
# setup_context_structure.py -- no need to copy them

# 4. Setup environment
gcloud config set project agentic-2026-493108
gcloud auth application-default login

uv init
uv add google-genai google-adk google-cloud-aiplatform

# 5. Run setup once — replace 2 and 9 with your course and lesson
python3 manageskills/setup_context_structure.py --course 2 --lesson 9


# 6. Generate lesson context (3 runs)
python3 manageskills/ai_md_converter.py --type lesson   --lesson L2
python3 manageskills/ai_md_converter.py --type exercise --lesson L2
python3 manageskills/ai_md_converter.py --type plan     --lesson L2


# 7. Initialize GitHub
git init
git remote add origin git@github.com:datai-wiss-dom/<lesson_repo>.git
git add .
git commit -m "L2 initial setup from Udacity starter code"
git push -u origin main
```

# 8. Start coding

```
claude
```

### Starting each exercise

Use this prompt every time — no need to re-explain context to the AI:

**Claude Code / Gemini CLI:**


```
Implement the exercise following .claude/current/lesson.md,
.claude/current/exercise.md and .claude/current/plan.md.
Read the existing starter code first before writing anything.
```


**Antigravity:**


```
Implement the exercise
```


> The context engineering system means CLAUDE.md, GEMINI.md and
> AGENTS.md already carry all project context. The AI arrives
> oriented — stack, rules, lesson position, exercise requirements.
> Never re-explain these manually.

### After implementing each exercise

Run these three commands in order in Claude Code:

**Step 1: Add observability**

```
/observe
```

Adds BigQueryAgentAnalyticsPlugin to your agent.
Verifies events stream to BigQuery.
Saves LLMAsJudge scores to .claude/current/eval_results.md

**Step 2: Run full evaluation**

```
/eval
```

Stage 1: agents-cli eval run (local tests)
Stage 2: BigQuery LLM-as-Judge quality gates
Stage 3: Regression detection SQL
Saves results to .claude/current/eval_results.md
All three stages must pass before proceeding.

**Step 3: Generate learning report**

```
/report
```

Reads your code + exercise.md + plan.md + eval_results.md
Generates comprehensive report with WHY not just WHAT
Saves to .claude/current/report.md
Review in IntelliJ before committing.

Step 4: Run security audit

```
/security
```

Scans credentials, packages, file access, MCP servers.
Fix any FAIL findings before committing.
WARN findings are non-critical but should be reviewed.

After all four commands pass:

### Completing a lesson and tagging


```bash
git add .
git commit -m "L2 complete - report + eval results"
git tag L2-complete
git push origin main
git push origin L2-complete
```


To return to any lesson exact state:


```bash
git checkout L2-complete
```


-----


## Antigravity quota interruption


```
/handoff    ← type in Antigravity chat
claude      ← reads HANDOFF.md, continues seamlessly
```


`HANDOFF.md` is automatically deleted on the next lesson run of `ai_md_converter.py`.


-----


## Stack


|Layer          |Tool                                                   |
|---------------|-------------------------------------------------------|
|Language       |Python 3.13                                            |
|Package manager|uv                                                     |
|Agent framework|Google ADK                                             |
|LLM            |Vertex AI Gemini (gemini-2.5-flash)                    |
|Deployment     |Cloud Run / Vertex AI Agent Engine                     |
|IDE            |IntelliJ IDEA 2025.3                                   |
|AI tools       |Claude Code CLI · Gemini CLI · Antigravity · agents-cli|
|Extensions     |data-agent-kit-starter-pack (optional) · Claude Code: /plugin install (Method A) · Gemini CLI: gemini extensions install (Method B) · Full setup: OPS.md Section 1.11|


-----


## Key insight


This project applies **context engineering** — encoding project knowledge into structured files so AI tools arrive already oriented.


The system scales across:


- 56 lessons across 4 courses
- 4 different AI coding tools
- Quota interruptions with zero work loss
- ~500 tokens per session instead of 100k


-----


## Operations & Maintenance


See [`manageskills/OPS.md`](manageskills/OPS.md) for:


- Reset procedure (clean slate)
- Troubleshooting steps
- Setup verification checklist


-----


## Optional Extensions

### data-agent-kit-starter-pack

Works across Gemini CLI, Claude Code, and Antigravity.
Adds GCP data engineering expertise automatically.

Install once on your machine — see
[manageskills/OPS.md](manageskills/OPS.md) for
installation guide.

This is optional. All tools work without it.

Most relevant from Course 3 onwards.

