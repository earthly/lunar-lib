#!/bin/bash
set -e

# Detect manifest-cli executions in CI and record metadata.
# This runs native on the CI runner — avoid jq and other non-standard deps.

# Extract the command string from LUNAR_CI_COMMAND JSON array
# LUNAR_CI_COMMAND is like: ["manifest-cli","sbom","--name","my-app"]
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')

# Try to get the manifest-cli version
VERSION=""
if command -v manifest-cli &>/dev/null; then
    VERSION=$(manifest-cli --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")
elif command -v manifest &>/dev/null; then
    VERSION=$(manifest --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")
fi

# Write source metadata
lunar collect ".sbom.cicd.source.tool" "manifest-cli"
lunar collect ".sbom.cicd.source.integration" "ci"
if [ -n "$VERSION" ]; then
    lunar collect ".sbom.cicd.source.version" "$VERSION"
fi

# Write command to cmds array (Lunar auto-concatenates arrays)
if [ -n "$VERSION" ]; then
    lunar collect -j ".sbom.cicd.cmds" "[{\"cmd\":\"$CMD_STR\",\"version\":\"$VERSION\"}]"
else
    lunar collect -j ".sbom.cicd.cmds" "[{\"cmd\":\"$CMD_STR\"}]"
fi
