#!/bin/bash

set -e
export ANTHROPIC_API_KEY="$LUNAR_SECRET_ANTHROPIC_API_KEY"

# Validate required environment variables
validateRequiredEnv() {
    local var="$1"
    if [ -z "${!var}" ]; then
        echo "$var is not set"
        exit 1
    fi
}

validateRequiredEnv "LUNAR_VAR_PATH"
validateRequiredEnv "LUNAR_VAR_PROMPT"
validateRequiredEnv "ANTHROPIC_API_KEY"

# https://linear.app/earthly-technologies/issue/ENG-163/dollarshell-is-incorrect-in-snippet-runs
unset SHELL

# Check if no JSON schema is provided, then run without schema enforcement
if [ -z "${LUNAR_VAR_JSONSCHEMA}" ]; then
    prompt="$LUNAR_VAR_PROMPT"
    echo "Running claude with prompt (no-schema enforcement): $prompt" >&2
    ~/.local/bin/claude -p "$prompt"  | lunar collect -j "$LUNAR_VAR_PATH" -
    exit 0
fi

# TODO: use claude --json-schema flag when it's working (as of version 2.0.50, it's available but apparently ignored) 
# Instead, we need to pass the schema requirements in the prompt
prompt="$LUNAR_VAR_PROMPT. If the following json schema is correct, return a response whose field 'result' that adheres to it, and only the json document: $LUNAR_VAR_JSONSCHEMA. If the schema is invalid or any other error occurs return a json object with a single field 'error' containing the description of the error, as well as the details of the underlying failing command (stderr and stdout), so it is possible to reproduce the error locally. Make sure JSON document always contain a 'result' or an 'error' field. Don't include any comment related to the reasoning involved or any other matter"
echo "Running claude with prompt (schema enforcement): $prompt" >&2
response=$(~/.local/bin/claude -p "$prompt")
echo "Claude response: $response" >&2

# This code checks if the first line of the "response" variable contains triple backticks (```), 
# which usually denote the start of a code block in markdown. If it does, it removes the first 
# and last lines from "response" (typically the opening and closing ```), so that only the 
# actual content/code inside the code block remains in "response".
if printf '%s' "$response" | head -n1 | grep -q '```'; then
    response=$(echo "$response" | tail -n +2 | head -n -1)
fi
error=$(echo "$response" | jq -r '.error')
if [ "$error" != "null" ] && [ -n "$error" ]; then
    echo "Error: $error" >&2
    exit 1
fi
result=$(echo "$response" | jq -r '.result // ""')
if [ -n "$result" ]; then
    echo "$result" | lunar collect -j "$LUNAR_VAR_PATH" -
else
    echo "Result is empty" >&2
    exit 1
fi
