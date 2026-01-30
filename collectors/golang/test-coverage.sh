#!/bin/bash
set -e

# Extract the coverage profile path from -coverprofile argument
# Hook pattern guarantees -coverprofile is present in LUNAR_CI_COMMAND (JSON array)
index=$(echo "$LUNAR_CI_COMMAND" | jq -r 'index("-coverprofile")')
coverprofile_path=$(echo "$LUNAR_CI_COMMAND" | jq -r --argjson idx "$index" '.[$idx + 1]')

if [[ -z "$coverprofile_path" || "$coverprofile_path" == "null" ]]; then
  echo "Could not extract coverprofile path from command"
  exit 1
fi

# Check if coverage file exists
if [[ ! -f "$coverprofile_path" ]]; then
  echo "Coverage profile not found: $coverprofile_path"
  exit 1
fi

# Extract total percentage
coverage_pct=$(go tool cover -func="$coverprofile_path" 2>/dev/null | awk '/^total:/ {print $NF}' | sed 's/%$//' || echo "0")

# Collect to .lang.go.tests.coverage (language-specific)
jq -n \
  --argjson percentage "$coverage_pct" \
  --arg profile_path "$coverprofile_path" \
  --rawfile raw_profile "$coverprofile_path" \
  '{
    percentage: $percentage,
    profile_path: $profile_path,
    native: {
      profile: $raw_profile
    },
    source: {
      tool: "go cover",
      integration: "ci"
    }
  }' | lunar collect -j ".lang.go.tests.coverage" -

# Also write to normalized .testing.coverage for cross-language policies
jq -n \
  --argjson percentage "$coverage_pct" \
  '{
    percentage: $percentage,
    source: {
      tool: "go cover",
      integration: "ci"
    }
  }' | lunar collect -j ".testing.coverage" -
