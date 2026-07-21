# Operations & Maintenance
# Udacity Google Agentic AI Engineer

**Author:** Wissem Khlifi

This file covers everything needed to operate this project:
- Section 1: Machine setup (once per machine, Debian Linux)
- Section 2: Per-lesson project setup
- Section 3: Per-lesson workflow
- Section 4: Reset -- clean slate
- Section 5: Troubleshooting

---

## 1. Machine Setup (Once Per Machine -- Debian Linux)

Do this once on a fresh Debian Linux machine.
Never repeat per project.

---

### 1.1 System Prerequisites

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y \
  curl wget git build-essential \
  python3 python3-pip python3-venv \
  ca-certificates gnupg lsb-release
```

---

### 1.2 Google Cloud CLI (gcloud)

```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud --version
gcloud auth login
gcloud auth application-default login
gcloud config set project agentic-2026-493108
gcloud auth application-default print-access-token
```

ADC (Application Default Credentials) is required by all
scripts and AI tools. Always run
`gcloud auth application-default login` on a new machine.

---

### 1.3 uv (Python Package Manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version
```

CRITICAL: Always use `uv add` not `pip install`.
Never use pip install directly.

---

### 1.4 Node.js (required by Claude Code CLI and Gemini CLI)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
node --version
npm --version
mkdir -p ~/.npm-global
npm config set prefix ~/.npm-global
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

Node.js must be version 20+.
Configure npm prefix to avoid permission errors.
Never use sudo npm install.

---

### 1.5 Git + SSH Keys for GitHub

```bash
sudo apt-get install -y git
git config --global user.name "Wissem Khlifi"
git config --global user.email "your@email.com"
git config --global init.defaultBranch main
ssh-keygen -t ed25519 -C "your@email.com"
cat ~/.ssh/id_ed25519.pub
# Add output to GitHub Settings > SSH Keys
ssh -T git@github.com
```

---

### 1.6 IntelliJ IDEA 2025.3

Download from: https://www.jetbrains.com/idea/download/
Choose Linux .tar.gz (Community or Ultimate Edition).

```bash
tar -xzf ideaIU-*.tar.gz -C ~/apps/
~/apps/idea-*/bin/idea.sh
```

Plugins to install from JetBrains Marketplace:
- Python plugin
- Gemini CLI Companion (for Gemini CLI IDE integration)

NOTE: /ide install in Gemini CLI does NOT support
JetBrains auto-install. Install Gemini CLI Companion
manually from the JetBrains Marketplace.

---

### 1.7 Claude Code CLI

```bash
# Native installer for Debian/Ubuntu (no Node.js required)
curl -fsSL https://claude.ai/install.sh | sh
claude --version

# Configure global settings (do once after install)
mkdir -p ~/.claude
cat > ~/.claude/settings.json << 'EOF'
{
  "idleTimeoutMs": 300000
}
EOF

claude
```

Primary AI coding tool. Reads CLAUDE.md and
.claude/current/ automatically.
Requires paid Anthropic account (Claude Pro or Max).

idleTimeoutMs: 300000 raises the stream idle timeout to
5 minutes. Required for /report and other skills that
generate long responses. Without it, Claude Code cuts
the stream mid-response with "Stream idle timeout".

---

### 1.8 Gemini CLI

```bash
# Requires Node.js 20+ (see 1.4)
npm install -g @google/gemini-cli
gemini --version

# Configure model
mkdir -p ~/.gemini
cat > ~/.gemini/settings.json << 'SETTINGS'
{
  "selectedModel": "gemini-2.5-flash",
  "security": {
    "auth": {
      "selectedType": "vertex-ai"
    }
  }
}
SETTINGS

# Launch and authenticate
gemini
# Select: vertex-ai authentication
# Verify: /auth
```

Uses Vertex AI ADC auth -- no API key needed.
Always set selectedModel to gemini-2.5-flash.
Reads GEMINI.md automatically from project root.

---

### 1.9 Google agents-cli

```bash
# Install and setup using uvx (included with uv)
# This is the ONLY agents-cli command you run directly
uvx google-agents-cli setup
agents-cli --version
```

agents-cli injects 7 ADK skills into Claude Code,
Gemini CLI, Antigravity, and Codex.
The setup command is the only one you run directly.
All other commands are invoked by your AI coding tool.
Always use: `agents-cli scaffold create <name>`
NOT: `agents-cli scaffold <name>`

---

### 1.10 Antigravity

Download from: https://antigravity.dev
Follow Linux installation instructions on the site.
Open your project folder in Antigravity.
It reads AGENTS.md automatically from project root.

Pre-GA tool. When quota runs out type /handoff in chat.
HANDOFF.md is written automatically via AGENTS.md rules.
Pass HANDOFF.md to claude or gemini to continue work.

---

### 1.11 data-agent-kit Extension

ONE-TIME PER MACHINE -- skip if already done.
Adds GCP data engineering MCP servers to Claude
Code CLI and skills to Gemini CLI.
NOT a Python package. Runs via Node.js/npx.
Python venv is irrelevant.

#### Method A: Claude Code CLI Plugin (recommended)

Run inside a claude session (Crostini only):
```
/plugin marketplace add https://github.com/gemini-cli-extensions/data-agent-kit-starter-pack#0.1.0
/plugin install data-agent-kit-starter-pack@data-agent-kit-starter-pack-marketplace
/reload-plugins
```
Expected: 1 plugin * 6 agents * 10 MCP servers

Then configure project IDs outside claude:
```bash
MCP_FILE="$HOME/.claude/plugins/cache/data-agent-kit-starter-pack-marketplace/data-agent-kit-starter-pack/0.1.0/.mcp.json"
jq '
  .mcpServers.datacloud_bigquery_toolbox.env.BIGQUERY_PROJECT = "agentic-2026-493108" |
  .mcpServers.datacloud_bigquery_toolbox.env.BIGQUERY_LOCATION = "us-central1" |
  .mcpServers.datacloud_spanner_toolbox.env.SPANNER_PROJECT = "agentic-2026-493108" |
  .mcpServers.datacloud_knowledge_catalog_toolbox.env.DATAPLEX_PROJECT = "agentic-2026-493108" |
  .mcpServers.datacloud_dataproc_toolbox.env.DATAPROC_PROJECT = "agentic-2026-493108" |
  .mcpServers.datacloud_dataproc_toolbox.env.DATAPROC_REGION = "us-central1" |
  .mcpServers.datacloud_serverless_spark_toolbox.env.SERVERLESS_SPARK_PROJECT = "agentic-2026-493108" |
  .mcpServers.datacloud_serverless_spark_toolbox.env.SERVERLESS_SPARK_LOCATION = "us-central1"
' "$MCP_FILE" > "$MCP_FILE.tmp" && mv "$MCP_FILE.tmp" "$MCP_FILE"
```
CRITICAL: empty project = silent failure.
Always verify BIGQUERY_PROJECT is set.

Verify inside claude:
```
/mcp
```
All 10 MCP servers should show as connected.

Crostini note:
Two Claude Code instances on this machine:
  /home/wissemk (Crostini)       USE THIS
  /usr/local/google/home/wissemk NOT for ADK
/plugin command only works in Crostini.

#### Method B: Gemini CLI Extension

```bash
gemini extensions install \
  https://github.com/gemini-cli-extensions/data-agent-kit-starter-pack \
  --ref 0.1.0 \
  --consent
gemini extensions list
```

OPTIONAL -- tools work without it.
Most relevant from Course 3 onwards.
If fails try without --ref:
  gemini extensions install <url> --consent

---

### 1.12 Verify Complete Machine Setup

```bash
gcloud --version
uv --version
git --version
node --version
npm --version
claude --version
gemini --version
agents-cli --version
gcloud auth application-default print-access-token | head -c 20
cat ~/.gemini/settings.json
cat ~/.claude/settings.json
gemini extensions list
# Verify Data Agent Kit (Method A):
claude mcp list
ssh -T git@github.com
```

All commands should return version numbers or success.

---

## 2. Per-Lesson Project Setup (Once Per Lesson)

Each Udacity lesson has its own starter code,
project structure, and GitHub repository.

**Step 1: Download Udacity starter code**
Download from Udacity workspace, open in IntelliJ.

**Step 2: Copy manageskills scripts**

```bash
cd ~/IdeaProjects/<new_lesson_project>
mkdir manageskills
cp ~/IdeaProjects/<prev>/manageskills/setup_context_structure.py manageskills/
cp ~/IdeaProjects/<prev>/manageskills/ai_md_converter.py manageskills/
cp ~/IdeaProjects/<prev>/README.md .
```

NOTE: OPS.md and SKILL_README.md are generated
automatically by setup_context_structure.py.
No need to copy them manually.

**Step 3: Initialize Python environment**

```bash
uv init
uv add google-genai google-adk google-cloud-aiplatform
```

**Step 4: GCP auth (required before ai_md_converter.py)**

```bash
gcloud config set project agentic-2026-493108
gcloud auth application-default login
```

**Step 5: Run context structure setup**

```bash
python3 manageskills/setup_context_structure.py --course 2 --lesson 9
# Replace 2 and 9 with your actual course and lesson numbers
```

Safe to run without GCP auth -- creates files only,
no cloud calls. GCP auth is only needed for Step 7.

**Step 6: Initialize GitHub**

```bash
git init
git remote add origin git@github.com:datai-wiss-dom/<repo>.git
git add .
git commit -m "L<N> initial setup from Udacity starter code"
git push -u origin main
```

**Step 7: Create BigQuery dataset (once per GCP project)**

This step runs ONCE across all lessons. One shared dataset
holds all lesson tables (e.g. c2_l9_agent_events).
Skip this step if agent_analytics dataset already exists.

```bash
bq mk \
  --dataset \
  --location=US \
  --description="ADK Agent Analytics - one table per lesson" \
  agentic-2026-493108:agent_analytics

# Verify
bq ls --project_id=agentic-2026-493108
# Should show: agent_analytics
```

Each lesson gets its own BigQuery table (e.g. c2_l9_agent_events),
auto-created by the plugin on first agent run per lesson.

**Step 8: Generate context files (needs GCP auth)**

```bash
python3 manageskills/ai_md_converter.py --type lesson   --lesson L1
python3 manageskills/ai_md_converter.py --type exercise --lesson L1
python3 manageskills/ai_md_converter.py --type plan     --lesson L1
```

---

## 3. Per-Lesson Workflow (Every Lesson)

**Step 1: Generate context files (before coding)**

```bash
python3 manageskills/ai_md_converter.py --type lesson   --lesson L2
python3 manageskills/ai_md_converter.py --type exercise --lesson L2
python3 manageskills/ai_md_converter.py --type plan     --lesson L2
```

The lesson run automatically archives, deletes stale
HANDOFF.md, and updates CLAUDE.md, GEMINI.md, course-map.md.

**Step 2: Start coding**

```bash
claude
```

Prompt to use every time:

```
Implement the exercise following .claude/current/lesson.md,
.claude/current/exercise.md and .claude/current/plan.md.
Read the existing starter code first before writing anything.
```

**Step 2b: Add observability after implementing**

```
/observe
```

This invokes the observe skill in Claude Code. It adds
BigQueryAgentAnalyticsPlugin to App() in your agent,
installs dependencies, and sets up evaluation pipeline.
Run this every lesson after the exercise is implemented.

**Step 3: Generate learning report (after coding)**

Paste into Claude Code after implementation is complete:

```
The exercise is complete. Now generate a learning report
and save it to .claude/current/report.md with these sections:

## What was built
## Concepts and Design -- explain WHY each ADK concept was chosen
## Implementation walkthrough -- how it works step by step
## Best practices applied -- what was done well and why
## Gaps for production readiness -- what is missing and how to fix
## Key learnings -- 3-5 bullet points for the learner

Be educational -- explain WHY every decision was made,
not just WHAT was built. Reference specific files and classes.
```

Review report.md in IntelliJ before committing.

**Step 3b: Run security audit before committing**

```
/security
```

Runs 6 audits: credentials, gitignore, packages,
file access, MCP servers, environment variables.
Fix any FAIL findings before committing.
WARN findings do not block commit but review them.

**Step 4: Commit and tag**

```bash
git add .
git commit -m "L2 complete - observability + verified report"
git tag L2-complete
git push origin main
git push origin L2-complete
```

**Step 5: Antigravity quota interruption**

```
/handoff    <- type in Antigravity chat
claude      <- reads HANDOFF.md, continues seamlessly
```

---

## 4. Reset -- Clean Slate

Use this when context structure needs to be rebuilt.

### Step 1 -- Delete everything the script created

```bash
cd ~/IdeaProjects/<your_lesson_project>
rm -f CLAUDE.md GEMINI.md AGENTS.md HANDOFF.md
rm -rf .claude .agent docs
rm -f .gitignore
```

### Step 2 -- Verify clean

```bash
ls -la
```

Should only show project files, not generated context files.
Should NOT show: CLAUDE.md GEMINI.md AGENTS.md .claude/ .agent/ docs/

### Step 3 -- Run setup again

```bash
python3 manageskills/setup_context_structure.py --course 2 --lesson 9
# Replace 2 and 9 with your actual course and lesson numbers
```

### Step 4 -- Regenerate lesson context

```bash
python3 manageskills/ai_md_converter.py --type lesson   --lesson L1
python3 manageskills/ai_md_converter.py --type exercise --lesson L1
python3 manageskills/ai_md_converter.py --type plan     --lesson L1
```

Replace L1 with your current lesson number.

### Step 5 -- Verify

```bash
ls -la .claude/current/
cat CLAUDE.md | grep "Lesson:"
cat GEMINI.md | grep "HANDOFF"
```

---

## 5. Troubleshooting

### exec: python not found

```bash
python3 manageskills/setup_context_structure.py
# Or add alias:
echo "alias python=python3" >> ~/.bashrc
source ~/.bashrc
```

### ERROR: google-genai not found

```bash
uv add google-genai
```

### ERROR during conversion from ai_md_converter.py

```bash
gcloud auth application-default login
gcloud config set project agentic-2026-493108
# Check Vertex AI API is enabled in GCP console
```

### Script creates files in wrong directory

Make sure PROJECT_ROOT in both scripts is:
```python
PROJECT_ROOT = Path(__file__).parent.parent
```
Not Path.cwd()

### /report (or other skill) fails with "Stream idle timeout"

Claude Code cuts the stream when no tokens arrive for too
long. Happens with skills that generate long responses.

```bash
# Check current setting
cat ~/.claude/settings.json

# Fix: set idle timeout to 5 minutes
cat > ~/.claude/settings.json << 'EOF'
{
  "idleTimeoutMs": 300000
}
EOF
```

This is a global setting -- apply once per machine.
If ~/.claude/settings.json already has other keys,
add "idleTimeoutMs": 300000 without removing them.

---

### HANDOFF.md keeps getting committed

```bash
echo "HANDOFF.md" >> .gitignore
git rm --cached HANDOFF.md
git add .gitignore
git commit -m "gitignore HANDOFF.md"
git push
```

---

## Setup Verification Checklist

```bash
ls CLAUDE.md GEMINI.md AGENTS.md .gitignore
ls .claude/current/
ls .claude/commands/
ls .agent/rules/ .agent/workflows/
ls docs/archive/ docs/reference/
grep "HANDOFF" CLAUDE.md
grep "HANDOFF.md exists" GEMINI.md
grep ".claude/current" .gitignore
grep "HANDOFF.md" .gitignore
grep ".env" .gitignore
python3 -c "from pathlib import Path; print(Path('manageskills/setup_context_structure.py').parent.parent.resolve())"
```
