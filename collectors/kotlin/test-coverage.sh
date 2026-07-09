#!/bin/bash
set -e

# CI collector — extracts coverage from Kover or JaCoCo XML reports after a
# Gradle/Maven test run. Both tools emit JaCoCo-style XML whose report-level
# aggregate is the LAST <counter type="LINE" missed=".." covered=".."/> in the
# file, so coverage% = covered / (covered + missed) * 100.
#
# This hook fires on gradle/mvn test, which also run in Java/Scala repos, and
# JaCoCo is not Kotlin-specific — so gate on *.kt / *.kts source presence to
# avoid writing .lang.kotlin into a non-Kotlin component.
if ! { git ls-files '*.kt' '*.kts' 2>/dev/null | grep -q . \
    || find . \( -name '*.kt' -o -name '*.kts' \) -not -path '*/build/*' 2>/dev/null | head -1 | grep -q .; }; then
    echo "No Kotlin source files detected, skipping coverage"
    exit 0
fi
#
# Common report locations:
#   build/reports/kover/report.xml                     (Kover 0.7+)
#   build/reports/kover/xml/report.xml                 (older Kover)
#   build/reports/jacoco/test/jacocoTestReport.xml     (Gradle + JaCoCo)
#   target/site/jacoco/jacoco.xml                      (Maven + JaCoCo)

tool=""
xml_path=""

# Prefer Kover (Kotlin-native), then JaCoCo, at their conventional paths.
for candidate in \
    "build/reports/kover/report.xml" \
    "build/reports/kover/xml/report.xml"; do
    if [[ -f "$candidate" ]]; then xml_path="$candidate"; tool="kover"; break; fi
done

if [[ -z "$xml_path" ]]; then
    for candidate in \
        "build/reports/jacoco/test/jacocoTestReport.xml" \
        "target/site/jacoco/jacoco.xml"; do
        if [[ -f "$candidate" ]]; then xml_path="$candidate"; tool="jacoco"; break; fi
    done
fi

# Fallback: search the tree (multi-module / custom report paths).
if [[ -z "$xml_path" ]]; then
    xml_path=$(find . -type f -path '*kover*' -name '*.xml' -not -path '*/node_modules/*' 2>/dev/null | head -1)
    [[ -n "$xml_path" ]] && tool="kover"
fi
if [[ -z "$xml_path" ]]; then
    xml_path=$(find . -type f \( -name "jacocoTestReport.xml" -o -name "jacoco.xml" \) -not -path '*/node_modules/*' 2>/dev/null | head -1)
    [[ -n "$xml_path" ]] && tool="jacoco"
fi

[[ -n "$xml_path" && -f "$xml_path" ]] || { echo "No Kover/JaCoCo XML report found, exiting"; exit 0; }

# Report-level aggregate = last matching counter. Prefer LINE, fall back to INSTRUCTION.
counter=$(grep -oE '<counter type="LINE"[^>]*>' "$xml_path" 2>/dev/null | tail -1)
[[ -z "$counter" ]] && counter=$(grep -oE '<counter type="INSTRUCTION"[^>]*>' "$xml_path" 2>/dev/null | tail -1)
[[ -n "$counter" ]] || { echo "No coverage counters in $xml_path, exiting"; exit 0; }

missed=$(echo "$counter" | sed -n 's/.*missed="\([0-9]*\)".*/\1/p')
covered=$(echo "$counter" | sed -n 's/.*covered="\([0-9]*\)".*/\1/p')

coverage_pct=$(awk -v m="${missed:-0}" -v c="${covered:-0}" 'BEGIN {
    total = m + c;
    if (total <= 0) exit 1;
    printf "%.1f", (c * 100) / total;
}') || { echo "Coverage counters empty in $xml_path, exiting"; exit 0; }

if [[ -n "$coverage_pct" && -n "$tool" ]]; then
    lunar collect -j ".lang.kotlin.tests.coverage.percentage" "$coverage_pct"
    lunar collect ".lang.kotlin.tests.coverage.source.tool" "$tool" \
                  ".lang.kotlin.tests.coverage.source.integration" "ci"
    # Mirror to the cross-language normalized path.
    lunar collect -j ".testing.coverage.percentage" "$coverage_pct"
    lunar collect ".testing.coverage.source.tool" "$tool" \
                  ".testing.coverage.source.integration" "ci"
fi
