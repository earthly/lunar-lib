#!/bin/bash

argument="./..."
exists=$(echo "$LUNAR_HOOK_CMD" | jq -e --arg val "$argument" 'index($val) != null')
if [[ $? -eq 0 ]]; then
    lunar collect .lang.go.tests.run recursive
else
    lunar collect .lang.go.tests.run package
fi

