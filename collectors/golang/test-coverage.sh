#!/bin/bash
set -e

# CI collector - runs native on CI runner, avoid jq and heavy dependencies

# Convert LUNAR_CI_COMMAND from JSON array to string if needed
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

# Extract -coverprofile path from command args using native bash
coverprofile_path=""
prev=""
for arg in $CMD_STR; do
  if [[ "$prev" == "-coverprofile" ]]; then
    coverprofile_path="$arg"
    break
  fi
  # Also handle -coverprofile=path format
  if [[ "$arg" == -coverprofile=* ]]; then
    coverprofile_path="${arg#-coverprofile=}"
    break
  fi
  prev="$arg"
done

if [[ -z "$coverprofile_path" || ! -f "$coverprofile_path" ]]; then
  exit 0
fi

# Extract total percentage
coverage_pct=$(go tool cover -func="$coverprofile_path" 2>/dev/null | awk '/^total:/ {print $NF}' | sed 's/%$//' || echo "")

if [[ -n "$coverage_pct" ]]; then
  # Collect coverage percentage and profile path as individual fields
  lunar collect -j ".lang.go.tests.coverage.percentage" "$coverage_pct"
  lunar collect ".lang.go.tests.coverage.profile_path" "$coverprofile_path"

  # Collect raw profile content as a string via stdin
  cat "$coverprofile_path" | lunar collect ".lang.go.tests.coverage.native.profile" -

  # Source metadata
  lunar collect ".lang.go.tests.coverage.source.tool" "go cover" \
               ".lang.go.tests.coverage.source.integration" "ci"
fi
