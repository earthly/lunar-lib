#!/bin/bash
set -e

# CI collector — extracts coverage from excoveralls output or mix test --cover.
#
# excoveralls typically writes to:
#   cover/excoveralls.json            (when `mix coveralls.json` is used)
#   cover/excoveralls.html or .lcov   (other formats)
# plain `mix test --cover` prints a "[TOTAL]" percentage summary but does
# not persist a machine-readable report.

# Convert LUNAR_CI_COMMAND from JSON array to string if needed
CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

coverage_pct=""
tool=""

# Prefer the excoveralls JSON report if it exists.
if [[ -f "cover/excoveralls.json" ]]; then
    tool="excoveralls"
    # excoveralls source_files[].coverage is an array of hit counts with nulls
    # for non-code lines. Covered = entries > 0; relevant = entries != null.
    coverage_pct=$(jq -r '
        [.source_files[].coverage[]] as $all
        | ($all | map(select(. != null))) as $relevant
        | ($relevant | map(select(. > 0))) as $covered
        | if ($relevant | length) == 0 then ""
          else ((($covered | length) * 10000 / ($relevant | length) | floor) / 100 | tostring)
          end
    ' cover/excoveralls.json 2>/dev/null || true)
fi

# Fallback for `mix coveralls.*` variants — parse stdout if the command was coveralls.
if [[ -z "$coverage_pct" ]] && [[ "$CMD_STR" == *"coveralls"* ]]; then
    tool="excoveralls"
    if [[ -n "$LUNAR_CI_OUTPUT" ]]; then
        coverage_pct=$(echo "$LUNAR_CI_OUTPUT" | sed -n 's/.*\[TOTAL\][[:space:]]*\([0-9][0-9]*\.[0-9]*\)%.*/\1/p' | tail -1 || true)
    fi
fi

# Fallback for `mix test --cover`.
if [[ -z "$coverage_pct" ]] && [[ "$CMD_STR" == *"test"* ]] && [[ "$CMD_STR" == *"--cover"* ]]; then
    tool="mix test --cover"
    if [[ -n "$LUNAR_CI_OUTPUT" ]]; then
        coverage_pct=$(echo "$LUNAR_CI_OUTPUT" | sed -n 's/.*[[:space:]]\([0-9][0-9]*\.[0-9]*\)%[[:space:]]*|[[:space:]]*Total.*/\1/p' | tail -1 || true)
    fi
fi

if [[ -n "$coverage_pct" ]] && [[ -n "$tool" ]]; then
    lunar collect -j ".lang.elixir.tests.coverage.percentage" "$coverage_pct"
    lunar collect ".lang.elixir.tests.coverage.source.tool" "$tool" \
                  ".lang.elixir.tests.coverage.source.integration" "ci"
    # Mirror to the cross-language normalized path.
    lunar collect -j ".testing.coverage.percentage" "$coverage_pct"
    lunar collect ".testing.coverage.source.tool" "$tool" \
                  ".testing.coverage.source.integration" "ci"
fi
