#!/bin/bash
set -e

# Read JUnit XML test reports when a Maven/Gradle build's JVM exits and record the
# totals. Runs native on the CI runner, so it sticks to bash, find and awk.
#
# Reports read, relative to the build's working directory (any depth), for the
# build tool that just ran, so a job that tests with both doesn't count twice:
#   Maven:  */target/surefire-reports/TEST-*.xml, */target/failsafe-reports/TEST-*.xml
#   Gradle: */build/test-results/<task>/TEST-*.xml
# Only files directly in those directories count: TestNG also writes its own
# copy of every suite to surefire-reports/junitreports/, which would double-count.
#
# Totals come from counting <testcase> elements, not <testsuite tests=...>:
# Surefire's rerunFailingTestsCount rewrites a rerun class's totals to the rerun
# only. A testcase failed if it has a <failure> or <error> child (Gradle reports
# an unexpected exception as <failure>, Surefire as <error>) and was skipped if
# it has <skipped>; flakyFailure/rerunFailure/rerunError are earlier attempts.
# Splitting records on "<" is safe because XML only allows a literal "<" inside
# CDATA and comments, which are skipped until they close.

# The hooked command is the build's JVM; Gradle's launch scripts pass -Dorg.gradle.appname.
case "${LUNAR_CI_COMMAND:-}" in
    *-Dorg.gradle.appname=*)
        tool=gradle
        report_dirs=(-path '*/build/test-results/*' ! -path '*/build/test-results/*/*/*') ;;
    *)
        tool=maven
        report_dirs=(\( -path '*/target/surefire-reports/*' -o -path '*/target/failsafe-reports/*' \)
            ! -path '*/target/surefire-reports/*/*' ! -path '*/target/failsafe-reports/*/*') ;;
esac

reports=()
while IFS= read -r -d '' f; do
    reports+=("$f")
done < <(find . \( -name .git -o -name node_modules \) -prune -o -type f -name 'TEST-*.xml' "${report_dirs[@]}" -print0 2>/dev/null)

if [[ ${#reports[@]} -eq 0 ]]; then
    echo "No JUnit XML reports found, skipping test results collection" >&2
    exit 0
fi

# shellcheck disable=SC2016  # $0 etc. belong to the awk program
count_testcases='
    function close_case() {
        if (open) { if (failed) f++; else if (skipped) s++ }
        open = 0
    }
    BEGIN { RS = "<" }
    FNR == 1 { close_case(); in_cdata = 0; in_comment = 0 }
    in_cdata   { if (index($0, "]]>")) in_cdata = 0; next }
    in_comment { if (index($0, "-->")) in_comment = 0; next }
    /^!\[CDATA\[/ { if (!index($0, "]]>")) in_cdata = 1; next }
    /^!--/        { if (!index($0, "-->")) in_comment = 1; next }
    {
        name = ""
        if (match($0, /^\/?[^ \t\r\n\/>]+/)) name = substr($0, RSTART, RLENGTH)
        if (name == "testcase") { close_case(); open = 1; failed = 0; skipped = 0; t++ }
        else if (name == "/testcase") close_case()
        else if (open && (name == "failure" || name == "error")) failed = 1
        else if (open && name == "skipped") skipped = 1
    }
    END { close_case(); printf "%d %d %d\n", t, f, s }
'

# Batches keep the argument list short. A failed batch aborts instead of
# recording partial totals, which could hide the failing tests.
total=0 failed=0 skipped=0
for ((i = 0; i < ${#reports[@]}; i += 200)); do
    if ! out=$(LC_ALL=C awk "$count_testcases" "${reports[@]:i:200}"); then
        echo "Could not parse the JUnit XML reports, not recording test results" >&2
        exit 1
    fi
    read -r t f s <<< "$out"
    total=$((total + ${t:-0})) failed=$((failed + ${f:-0})) skipped=$((skipped + ${s:-0}))
done

echo "Read ${#reports[@]} JUnit XML report(s): $total tests, $failed failed, $skipped skipped" >&2

if [[ $total -eq 0 ]]; then
    echo "Reports contain no test cases, skipping test results collection" >&2
    exit 0
fi

passed=$((total - failed - skipped))
all_passing=false
[[ $failed -eq 0 ]] && all_passing=true

counts_json="\"total\": $total, \"passed\": $passed, \"failed\": $failed, \"skipped\": $skipped"

json_str() {
    local v=${1//\\/\\\\}
    v=${v//\"/\\\"}
    printf '"%s"' "${v//[$'\t\r\n']/ }"
}
attempt=${LUNAR_CI_PIPELINE_RUN_ATTEMPT:-1}
[[ $attempt =~ ^[0-9]+$ ]] || attempt=1
step=${LUNAR_CI_STEP_INDEX:-0}
[[ $step =~ ^[0-9]+$ ]] || step=0

# The scalars hold the last build to finish at this commit, so with parallel jobs
# a green one can overwrite a red one. Arrays concatenate across builds, so
# .testing.runs keeps every build for testing.passing to check.
run="{\"pipeline\": $(json_str "${LUNAR_CI_PIPELINE_NAME:-}"), \"run_id\": $(json_str "${LUNAR_CI_PIPELINE_RUN_ID:-}"),"
run+=" \"attempt\": $attempt, \"job\": $(json_str "${LUNAR_CI_JOB_NAME:-}"), \"step\": $step, $counts_json, \"all_passing\": $all_passing}"

# .lang.java.tests.results (language-specific) and .testing.results (normalized,
# dual-write). .testing.source belongs to the test-scope sub-collector.
lunar collect -j \
    ".lang.java.tests.results" "{$counts_json, \"source\": {\"tool\": \"$tool\", \"integration\": \"ci\"}}" \
    ".testing.results" "{$counts_json}" \
    ".testing.all_passing" "$all_passing" \
    ".testing.runs" "[$run]"
