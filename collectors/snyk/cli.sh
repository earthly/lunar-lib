#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies

# Validate required environment variable
if [ -z "$LUNAR_CI_COMMAND" ]; then
    exit 0
fi

# Get the command that was run
CMD_RAW="$LUNAR_CI_COMMAND"

# Convert JSON array to string if needed (LUNAR_CI_COMMAND may be JSON array)
# Handle both: ["snyk", "test"] and "snyk test"
if [[ "$CMD_RAW" == "["* ]]; then
    # JSON array - extract elements without jq using sed/tr
    # Remove brackets and quotes, replace commas with spaces
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Skip if this looks like a git command
if echo "$CMD_STR" | grep -qE '^(/usr/bin/)?git\s'; then
    exit 0
fi

# Verify this command invokes snyk (but not just mentions it in a path or arg)
if ! echo "$CMD_STR" | grep -qE '(^|/|npx )snyk(\s|$)'; then
    exit 0
fi

# Detect category from command
CMD_LOWER=$(echo "$CMD_STR" | tr '[:upper:]' '[:lower:]')
if echo "$CMD_LOWER" | grep -q "snyk iac"; then
    CATEGORY="iac_scan"
elif echo "$CMD_LOWER" | grep -q "snyk container"; then
    CATEGORY="container_scan"
elif echo "$CMD_LOWER" | grep -q "snyk code"; then
    CATEGORY="sast"
else
    CATEGORY="sca"  # Default: snyk test = Open Source
fi

# Capture Snyk CLI version using the exact traced binary
SNYK_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-snyk}"
SNYK_VERSION=$("$SNYK_BIN" --version 2>/dev/null || echo "unknown")

# Sanitize command to redact potential secrets (tokens, credentials)
CMD_SAFE=$(echo "$CMD_STR" | sed -E \
    -e 's/(snyk auth) [^ ]+/\1 <redacted>/I' \
    -e 's/(--client-id|--client-secret|--token|--auth-token)(=| )[^ ]+/\1=<redacted>/Ig' \
    -e 's/(SNYK_TOKEN|SNYK_OAUTH_TOKEN)=[^ ]+/\1=<redacted>/Ig')

# Escape quotes in command for JSON
CMD_ESCAPED=$(echo "$CMD_SAFE" | sed 's/"/\\"/g')

# Write cicd command entry (no jq required)
# Note: multiple snyk commands in same CI run will each add to this structure
echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$SNYK_VERSION\"}]}" | \
    lunar collect -j ".$CATEGORY.native.snyk.cicd" -

# Write source metadata
lunar collect ".$CATEGORY.source.tool" "snyk"
lunar collect ".$CATEGORY.source.integration" "ci"
if [ -n "$SNYK_VERSION" ] && [ "$SNYK_VERSION" != "unknown" ]; then
    lunar collect ".$CATEGORY.source.version" "$SNYK_VERSION"
fi

# --- Raw results + normalized SCA counts ---
# The ci-after-command hook exposes the command line + exit code, NOT the
# scanner's stdout, so the only way to capture actual findings is to read the
# JSON file Snyk wrote via `--json-file-output=<path>`. Parse that path back
# out of the command itself (handles both `--json-file-output=x` and
# `--json-file-output x`). No flag → nothing to read, keep prior behavior.
RESULTS_FILE=""
if echo "$CMD_STR" | grep -qE '\-\-json-file-output[[:space:]=]+[^[:space:]]+'; then
    RESULTS_FILE=$(echo "$CMD_STR" | grep -oE '\-\-json-file-output[[:space:]=]+[^[:space:]]+' | head -1 | sed -E 's/--json-file-output[[:space:]=]+//')
fi

if [ -z "$RESULTS_FILE" ] || [ ! -f "$RESULTS_FILE" ]; then
    exit 0
fi

echo "Found Snyk JSON results at $RESULTS_FILE" >&2

# Preserve the raw Snyk JSON under native so policies can read fields we don't
# normalize (CVSS, references, exploit maturity, etc.).
lunar collect -j ".$CATEGORY.native.snyk.cicd.raw" - < "$RESULTS_FILE" || \
    echo "Warning: failed to collect raw Snyk output from $RESULTS_FILE" >&2

# Normalized severity counts only apply to the Open Source (sca) vulnerability
# schema produced by `snyk test`. `snyk code` (SARIF) and `snyk iac` use
# different shapes — capture their raw output above but don't normalize here.
if [ "$CATEGORY" != "sca" ]; then
    exit 0
fi

# Normalization needs jq (provided by install.sh). Degrade gracefully if it's
# missing — raw results are already captured above.
if ! command -v jq >/dev/null 2>&1; then
    echo "jq not available — skipping SCA normalization (raw results still captured)" >&2
    exit 0
fi

# Only normalize when the JSON actually carries a vulnerabilities array, i.e. a
# `snyk test` result rather than a `snyk monitor` snapshot.
HAS_VULNS=$(jq '[.. | objects | select(has("vulnerabilities") and (.vulnerabilities | type == "array"))] | length' "$RESULTS_FILE" 2>/dev/null || echo 0)
if [ "$HAS_VULNS" = "0" ] || [ -z "$HAS_VULNS" ]; then
    echo "No vulnerabilities array in Snyk JSON — skipping normalization" >&2
    exit 0
fi

# Snyk lists one entry per vulnerable dependency path, so dedupe by id for
# counts. The recursive walk handles single-project objects and the
# `--all-projects` array form alike. Severities are lowercase in Snyk JSON.
if NORMALIZED=$(jq -c '
  ([ .. | objects
       | select(has("vulnerabilities") and (.vulnerabilities | type == "array"))
       | .vulnerabilities[] ] | unique_by(.id)) as $vulns
  | {
      vulnerabilities: {
        critical: ([$vulns[] | select(.severity == "critical")] | length),
        high:     ([$vulns[] | select(.severity == "high")]     | length),
        medium:   ([$vulns[] | select(.severity == "medium")]   | length),
        low:      ([$vulns[] | select(.severity == "low")]      | length),
        total:    ($vulns | length)
      },
      findings: [ $vulns[] | {
        severity:    .severity,
        package:     .packageName,
        version:     (.version // null),
        ecosystem:   (.packageManager // null),
        cve:         (.identifiers.CVE[0]? // null),
        snyk_id:     .id,
        title:       .title,
        fix_version: (.fixedIn[0]? // null),
        fixable:     ((.fixedIn // []) | length > 0)
      } ],
      summary: {
        has_critical: ([$vulns[] | select(.severity == "critical")] | length > 0),
        has_high:     ([$vulns[] | select(.severity == "high")]     | length > 0),
        has_medium:   ([$vulns[] | select(.severity == "medium")]   | length > 0),
        has_low:      ([$vulns[] | select(.severity == "low")]      | length > 0),
        all_fixable:  ([$vulns[] | select((.fixedIn // []) | length == 0)] | length == 0)
      }
    }' "$RESULTS_FILE" 2>/dev/null); then
    echo "$NORMALIZED" | lunar collect -j ".sca" -
    echo "Collected SCA vulnerability counts from Snyk results" >&2
else
    echo "Warning: failed to parse Snyk JSON for normalization" >&2
fi
