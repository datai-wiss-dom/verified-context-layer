#!/usr/bin/env bash
#
# scripts/leak_scan.sh — pre-commit / pre-push hygiene for the PUBLIC repo.
#
# Scans the files that WOULD be published (tracked + untracked-but-not-ignored) for real
# deployment identifiers that must never leave .env. Gitignored files (.env, *.tfvars,
# channels.env, the evidence note, …) are excluded by design — they legitimately hold the
# real values.
#
# The values to protect are read from .env (gitignored) at runtime, so THIS committed script
# contains none of them (putting them here would itself be the leak).
#
# TOKEN MATCH — the important bit: we match the Slack token PATTERN ('xox?-' followed by real
# token-body characters), NOT the bare 'xoxb-' prefix. The bare prefix appears legitimately in
# infra/04_verify.sh's own token-format check (a comment and a string comparison); matching it
# cried wolf on every run, so the check stopped being read. Matching the pattern still catches
# a real token while ignoring the prefix literal.
#
# Exit 0 = clean; non-zero = a real identifier was found (prints file:line).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Load the identifiers to protect (only if .env is present; a public clone has no .env and
# falls back to the generic token-shape check).
set -a; source .env 2>/dev/null || true; set +a

pats=()
[[ -n "${VCL_PROJECT:-}"        ]] && pats+=("${VCL_PROJECT}")
[[ -n "${VCL_PROJECT_NUMBER:-}" ]] && pats+=("${VCL_PROJECT_NUMBER}")
[[ -n "${VCL_OWNER_EMAIL:-}"    ]] && pats+=("${VCL_OWNER_EMAIL}")
# Slack token PATTERN (xoxb/xoxa/xoxp/xoxr/xoxs + >=8 body chars) — never the bare prefix.
pats+=('xox[baprs]-[0-9A-Za-z]{8,}')

IFS='|'; PATTERN="${pats[*]}"; unset IFS

# Files that would be published: tracked + untracked-but-not-ignored (NUL-safe).
mapfile -d '' FILES < <(git ls-files -z; git ls-files -z --others --exclude-standard)
[[ ${#FILES[@]} -gt 0 ]] || { echo "leak scan: no files to scan."; exit 0; }

hits="$(printf '%s\0' "${FILES[@]}" | xargs -0 grep -nEI "${PATTERN}" 2>/dev/null || true)"
if [[ -n "${hits}" ]]; then
  echo "LEAK — real deployment identifiers found in files that would be committed:" >&2
  echo "${hits}" >&2
  exit 1
fi
echo "leak scan: CLEAN — no real project id / number / owner email / Slack token in published files."
