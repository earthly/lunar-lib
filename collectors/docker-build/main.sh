#!/bin/bash
set -e

# Convert command JSON array to string for simple pattern matching
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | jq -r 'join(" ")')

# Simple checks
HAS_LABEL_FLAG=false
HAS_GIT_SHA_LABEL=false

if [[ "$CMD_STR" == *"--label"* ]]; then
  HAS_LABEL_FLAG=true
  if [[ "$CMD_STR" == *"--label"*"git_sha"* ]] || [[ "$CMD_STR" == *"--label=git_sha"* ]]; then
    HAS_GIT_SHA_LABEL=true
  fi
fi

# If git SHA is missing, inject it and re-run the command
# Future versions of Lunar will have better support for this use case, e.g.: 
# lunar modify-cmd $CMD_STR --label "git_sha=$LUNAR_COMPONENT_GIT_SHA"
# if [[ "$HAS_GIT_SHA_IN_LABEL" == "false" ]]; then
#   # Add the git_sha label to the command
#   MODIFIED_CMD=$(echo "$LUNAR_CI_COMMAND" | jq '. + ["--label", "git_sha='$LUNAR_COMPONENT_GIT_SHA'"]')
  
#   # Execute the modified command
#   eval "$(echo "$MODIFIED_CMD" | jq -r 'join(" ")')"
  
#   HAS_GIT_SHA_IN_LABEL=true
# fi

# Collect the results as JSON array - Lunar will concatenate arrays from multiple runs
jq -n \
  --arg cmd "$CMD_STR" \
  --arg expected_git_sha "$LUNAR_COMPONENT_GIT_SHA" \
  --arg has_label_flag "$HAS_LABEL_FLAG" \
  --arg has_git_sha_label "$HAS_GIT_SHA_LABEL" \
  '[{cmd: $cmd, expected_git_sha: $expected_git_sha, has_label_flag: ($has_label_flag == "true"), has_git_sha_label: ($has_git_sha_label == "true")}]' | \
  lunar collect -j ".docker_build.builds" -
