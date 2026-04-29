#!/bin/bash
set -e

# CI collector — extracts coverage from scoverage XML reports after sbt or Mill
# test runs. scoverage typically writes:
#   target/scala-<ver>/scoverage-report/scoverage.xml          (sbt single-module)
#   target/scala-<ver>/scoverage-report/scoverage-aggregate.xml (sbt aggregate)
#   <module>/target/scala-<ver>/scoverage-report/scoverage.xml (sbt subprojects)
#   out/<module>/scoverage/xmlReport.dest/scoverage.xml        (Mill)

CMD_RAW="$LUNAR_CI_COMMAND"
if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

coverage_pct=""
tool=""

# Find the most recent scoverage report — multi-module repos produce several.
xml_path=""
if compgen -G "**/scoverage.xml" >/dev/null 2>&1 || \
   find . -type f -name "scoverage.xml" -not -path '*/node_modules/*' 2>/dev/null | head -1 | grep -q .; then
    xml_path=$(find . -type f \( -name "scoverage-aggregate.xml" -o -name "scoverage.xml" \) \
        -not -path '*/node_modules/*' 2>/dev/null \
        -printf "%T@ %p\n" 2>/dev/null | sort -rn | head -1 | awk '{print $2}')
fi

# scoverage XML root: <scoverage statement-rate="78.42" branch-rate="..." ...>
if [[ -n "$xml_path" ]] && [[ -f "$xml_path" ]]; then
    tool="scoverage"
    coverage_pct=$(sed -n 's|.*statement-rate="\([0-9.]*\)".*|\1|p' "$xml_path" | head -1)
fi

# Fallback: parse `[info] Statement coverage.: 78.40%` from sbt-scoverage stdout.
if [[ -z "$coverage_pct" ]] && [[ -n "$LUNAR_CI_OUTPUT" ]]; then
    pct=$(echo "$LUNAR_CI_OUTPUT" | sed -n 's/.*Statement[[:space:]]*coverage[^0-9]*\([0-9][0-9]*\.[0-9]*\)%.*/\1/p' | tail -1 || true)
    if [[ -n "$pct" ]]; then
        tool="scoverage"
        coverage_pct="$pct"
    fi
fi

if [[ -n "$coverage_pct" ]] && [[ -n "$tool" ]]; then
    lunar collect -j ".lang.scala.tests.coverage.percentage" "$coverage_pct"
    lunar collect ".lang.scala.tests.coverage.source.tool" "$tool" \
                  ".lang.scala.tests.coverage.source.integration" "ci"
    # Mirror to the cross-language normalized path.
    lunar collect -j ".testing.coverage.percentage" "$coverage_pct"
    lunar collect ".testing.coverage.source.tool" "$tool" \
                  ".testing.coverage.source.integration" "ci"
fi
