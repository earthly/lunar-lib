#!/bin/bash
set -e

# Captures sonar-scanner invocations in CI via a ci-after-command hook. Runs
# native on the CI runner, so no jq/yq dependencies. Mirrors the snyk/cli
# pattern: normalize the traced command, redact obvious secrets, extract the
# scanner version from the traced binary, and write one entry per invocation
# to .code_quality.native.sonarqube.cicd.cmds. The Lunar SDK concatenates
# repeated writes to array paths, so multiple invocations in the same CI run
# accumulate cleanly.

if [ -z "${LUNAR_CI_COMMAND:-}" ]; then
    exit 0
fi

CMD_RAW="$LUNAR_CI_COMMAND"

# Normalize JSON-array form (["sonar-scanner","-Dsonar.projectKey=..."]) into a
# plain string without invoking jq.
if [ "${CMD_RAW:0:1}" = "[" ]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Sanity check: the hook's binary-match should prevent this, but be defensive.
if ! echo "$CMD_STR" | grep -qE '(^|/)sonar-scanner(\s|$)'; then
    exit 0
fi

# Capture the scanner version using the exact traced binary path.
SCANNER_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-sonar-scanner}"
SCANNER_VERSION=$("$SCANNER_BIN" --version 2>/dev/null \
    | grep -oE '[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?' \
    | head -1 || echo "unknown")
[ -z "$SCANNER_VERSION" ] && SCANNER_VERSION="unknown"

# Redact tokens/passwords that users sometimes pass on the command line.
CMD_SAFE=$(echo "$CMD_STR" | sed -E \
    -e 's/(-Dsonar\.login)=[^ ]+/\1=<redacted>/Ig' \
    -e 's/(-Dsonar\.password)=[^ ]+/\1=<redacted>/Ig' \
    -e 's/(-Dsonar\.token)=[^ ]+/\1=<redacted>/Ig' \
    -e 's/(SONAR_TOKEN|SONARQUBE_TOKEN)=[^ ]+/\1=<redacted>/Ig')

# Escape quotes for inline JSON.
CMD_ESCAPED=$(echo "$CMD_SAFE" | sed 's/"/\\"/g')

echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$SCANNER_VERSION\"}]}" \
    | lunar collect -j ".code_quality.native.sonarqube.cicd" -

lunar collect ".code_quality.source.tool" "sonarqube"
lunar collect ".code_quality.source.integration" "ci"
if [ "$SCANNER_VERSION" != "unknown" ]; then
    lunar collect ".code_quality.source.version" "$SCANNER_VERSION"
fi
