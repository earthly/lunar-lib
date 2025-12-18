#!/bin/bash

if [[ -e CODEOWNERS ]]; then
  lunar collect -j "repo.codeowners.missing" false
  grep -vE '^(#|$)' CODEOWNERS | jq  --raw-input .  | jq --slurp . | lunar collect -j "repo.codeowners.content" -
else
    lunar collect -j "repo.codeowners.missing" true
fi
