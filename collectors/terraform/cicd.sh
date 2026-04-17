#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies.
# Records every terraform command with the Terraform CLI version.

# Convert LUNAR_CI_COMMAND from JSON array to string if needed
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Escape command for safe JSON embedding (backslashes then double quotes)
CMD_ESCAPED=$(echo "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Use the exact traced binary for version extraction
TERRAFORM_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-terraform}"

# `terraform version` prints e.g. "Terraform v1.9.8" on the first line
VERSION=$("$TERRAFORM_BIN" version 2>/dev/null | head -n1 | awk '{print $2}' | sed 's/^v//' || echo "")
VERSION_ESCAPED=$(echo "$VERSION" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Always collect the command; version may be empty
if [[ -n "$VERSION_ESCAPED" ]]; then
  echo "{\"cicd\":{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$VERSION_ESCAPED\"}],\"source\":{\"tool\":\"terraform\",\"integration\":\"ci\"}}}" | \
    lunar collect -j ".iac.native.terraform" -
else
  echo "{\"cicd\":{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\"}],\"source\":{\"tool\":\"terraform\",\"integration\":\"ci\"}}}" | \
    lunar collect -j ".iac.native.terraform" -
fi
