#!/bin/bash
set -e

# Run Claude CLI in review mode against PR diffs.
# Captures findings and writes to ai.native.claude.code_review.

export ANTHROPIC_API_KEY="$LUNAR_SECRET_ANTHROPIC_API_KEY"

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "LUNAR_SECRET_ANTHROPIC_API_KEY is required for run-code-review." >&2
  exit 1
fi

# Get the diff for this PR
if [ -z "$LUNAR_COMPONENT_BASE_BRANCH" ]; then
  echo "No base branch — run-code-review requires a PR context." >&2
  exit 0
fi

DIFF=$(git diff "origin/$LUNAR_COMPONENT_BASE_BRANCH...HEAD" 2>/dev/null || true)

if [ -z "$DIFF" ]; then
  jq -n '{ran: false, reason: "no diff"}' | lunar collect -j ".ai.native.claude.code_review" -
  exit 0
fi

# https://linear.app/earthly-technologies/issue/ENG-163/dollarshell-is-incorrect-in-snippet-runs
unset SHELL

# Run claude in review mode
PROMPT="Review this pull request diff. For each issue found, output JSON with fields: severity (error/warning/info), file, line (if applicable), and message. Output ONLY a JSON array of findings, no other text."

RESPONSE=$(echo "$DIFF" | ~/.local/bin/claude -p "$PROMPT" 2>/dev/null || true)

if [ -z "$RESPONSE" ]; then
  jq -n '{ran: true, findings_count: 0, findings: []}' | lunar collect -j ".ai.native.claude.code_review" -
  exit 0
fi

# Strip markdown code fences if present
if printf '%s' "$RESPONSE" | head -n1 | grep -q '```'; then
  RESPONSE=$(echo "$RESPONSE" | tail -n +2 | head -n -1)
fi

# Parse findings
FINDINGS=$(echo "$RESPONSE" | jq -c '.' 2>/dev/null || echo "[]")
if ! echo "$FINDINGS" | jq -e 'type == "array"' >/dev/null 2>&1; then
  FINDINGS="[]"
fi

COUNT=$(echo "$FINDINGS" | jq 'length')

jq -n \
  --argjson ran true \
  --argjson findings_count "$COUNT" \
  --argjson findings "$FINDINGS" \
  '{
    ran: $ran,
    findings_count: $findings_count,
    findings: $findings
  }' | lunar collect -j ".ai.native.claude.code_review" -
