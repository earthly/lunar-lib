#!/bin/bash
set -e
# Determine test scope based on command arguments
argument="./..."
if echo "$LUNAR_CI_COMMAND" | jq -e --arg val "$argument" 'index($val) != null' >/dev/null 2>&1; then
    lunar collect .lang.go.tests.scope recursive
else
    lunar collect .lang.go.tests.scope package
fi

