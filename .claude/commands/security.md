---
name: security
description: Run pre-commit security audit. Checks credentials, packages, file access, MCP servers. Non-blocking -- warns only.
---

# /security -- Pre-Commit Security Audit

Non-blocking. Run before every git commit.

## Audit 1: Credential scan
```bash
grep -rn --include='*.py' --include='*.json' \
  -E '(api_key|secret|password|token)=.{8,}' \
  . --exclude-dir='.venv' --exclude-dir='.git'
grep -rn '-----BEGIN' . \
  --exclude-dir='.venv' --exclude-dir='.git'
```
Expected: no output. Remove credentials found.

## Audit 2: .gitignore coverage
```bash
for p in '.env' 'HANDOFF.md' '.claude/current/' \
         '*.key' '*.pem' 'service_account*.json'; do
  grep -q "$p" .gitignore \
    && echo "OK: $p" \
    || echo "MISSING: $p -- add to .gitignore"
done
```

## Audit 3: Package trust check
Read pyproject.toml. Every package must be on
the trusted list in AGENTS.md Security Protocol
or explicitly approved by the developer.
Trusted: google-adk, google-cloud-*, google-genai,
google-auth, anthropic, bigquery-agent-analytics,
vertexai, pydantic, fastapi, uvicorn, httpx,
requests, pytest, python-dotenv, tabulate.
Any other package: ask developer before installing.
```bash
cat pyproject.toml
```

## Audit 4: Sensitive file access
```bash
grep -rn --include='*.py' \
  -E 'open\(.*(/etc/|~/.ssh|.aws|.config/gcloud)' \
  . --exclude-dir='.venv' --exclude-dir='.git'
grep -rn --include='*.py' \
  -E '(subprocess|os\.system|eval\(|exec\()' \
  . --exclude-dir='.venv' --exclude-dir='.git'
```
Review all output carefully.

## Audit 5: MCP server trust
```bash
find . -name '*.json' \
  -not -path './.venv/*' -not -path './.git/*' \
  | xargs grep -l 'mcp' 2>/dev/null
```
Only official Google MCP servers allowed.
Any other: ask developer to verify first.

## Audit 6: Env var usage
```bash
grep -rn --include='*.py' \
  'agentic-2026-493108' \
  . --exclude-dir='.venv' --exclude-dir='.git'
```
Project ID in .py files should use os.environ.

## Pre-commit checklist
- [ ] Audit 1: no credentials in files
- [ ] Audit 2: .gitignore covers sensitive files
- [ ] Audit 3: all packages trusted or approved
- [ ] Audit 4: no suspicious file access or eval
- [ ] Audit 5: MCP servers are official only
- [ ] Audit 6: project ID uses env vars in .py
