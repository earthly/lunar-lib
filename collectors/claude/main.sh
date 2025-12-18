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

echo "Running claude with prompt: $LUNAR_VAR_PROMPT"
~/.local/bin/claude -p "$LUNAR_VAR_PROMPT"  | lunar collect "$LUNAR_VAR_PATH" -
