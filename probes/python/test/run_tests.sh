#!/bin/sh
# test/run_tests.sh — harness for check-disallowed-deps.sh.
#
# Each case pipes a PreToolUse JSON payload through the check and asserts
# on exit code (0 = allow, 1 = block) and, for blocks, that the offending
# CVE is surfaced on stdout. No network, no real agent — pure stdin/stdout.

set -u

SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/scripts/check-disallowed-deps.sh"
PASS=0
FAIL=0
DETAILS=""
RES_EXIT=""
RES_OUT=""

run() {
    RES_OUT="$(printf '%s' "$1" | sh "$SCRIPT" 2>/dev/null)"
    RES_EXIT=$?
}

assert_exit() {
    name="$1"
    want="$2"
    if [ "$RES_EXIT" = "$want" ]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        DETAILS="${DETAILS}
  [FAIL] ${name}
         expected exit=${want}, got exit=${RES_EXIT} stdout=<${RES_OUT}>"
    fi
}

assert_block() {
    # exit 1 AND stdout mentions the expected CVE
    name="$1"
    cve="$2"
    if [ "$RES_EXIT" = "1" ] && printf '%s' "$RES_OUT" | grep -q "$cve"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        DETAILS="${DETAILS}
  [FAIL] ${name}
         expected block citing ${cve}, got exit=${RES_EXIT} stdout=<${RES_OUT}>"
    fi
}

# ============================================================
# requirements.txt — concrete == pins
# ============================================================

run '{"tool_input":{"file_path":"requirements.txt","content":"starlette==1.0.0"}}'
assert_block "starlette==1.0.0 in [0.8.3,1.0.1) -> block" "CVE-2026-48710"

run '{"tool_input":{"file_path":"requirements.txt","content":"starlette>=1.0.1"}}'
assert_exit "starlette>=1.0.1 (open range, not concrete) -> allow" 0

run '{"tool_input":{"file_path":"requirements.txt","content":"starlette==1.0.1"}}'
assert_exit "starlette==1.0.1 (== high, exclusive) -> allow" 0

run '{"tool_input":{"file_path":"requirements.txt","content":"starlette==0.8.3"}}'
assert_block "starlette==0.8.3 (== low, inclusive) -> block" "CVE-2026-48710"

run '{"tool_input":{"file_path":"requirements.txt","content":"starlette==0.8.0"}}'
assert_exit "starlette==0.8.0 (below low) -> allow" 0

run '{"tool_input":{"file_path":"requirements.txt","content":"urllib3==2.2.1"}}'
assert_block "urllib3==2.2.1 -> block" "CVE-2024-37891"

run '{"tool_input":{"file_path":"requirements.txt","content":"urllib3==2.2.2"}}'
assert_exit "urllib3==2.2.2 (== fix) -> allow" 0

run '{"tool_input":{"file_path":"requirements.txt","content":"numpy==1.25.0"}}'
assert_exit "numpy==1.25.0 (not in defaults) -> allow" 0

run '{"tool_input":{"file_path":"requirements.txt","content":"starlette"}}'
assert_exit "starlette (no version pin) -> allow" 0

run '{"tool_input":{"file_path":"requirements.txt","content":"requests == 2.31.0"}}'
assert_block "spaces around == -> block" "CVE-2024-35195"

# ============================================================
# Case-insensitivity + separator normalisation (PyPI rules)
# ============================================================

run '{"tool_input":{"file_path":"requirements.txt","content":"Jinja2==3.1.3"}}'
assert_block "Jinja2 mixed-case -> block" "CVE-2024-34064"

run '{"tool_input":{"file_path":"requirements.txt","content":"PYYAML==5.3.1"}}'
assert_block "PYYAML uppercase -> block" "CVE-2020-14343"

run '{"tool_input":{"file_path":"requirements.txt","content":"PyYAML==5.4"}}'
assert_exit "PyYAML==5.4 (== fix) -> allow" 0

# extras spec should not defeat the match
run '{"tool_input":{"file_path":"requirements.txt","content":"requests[security]==2.31.0"}}'
assert_block "requests[security]==2.31.0 -> block" "CVE-2024-35195"

# a different package that merely contains a disallowed name must not match
run '{"tool_input":{"file_path":"requirements.txt","content":"my-requests-helper==1.0.0"}}'
assert_exit "my-requests-helper (substring) -> allow" 0

# ============================================================
# pyproject.toml — caret/exact
# ============================================================

run '{"tool_input":{"file_path":"pyproject.toml","content":"starlette = \"^1.0.1\""}}'
assert_exit "pyproject caret ^1.0.1 (not concrete) -> allow" 0

run '{"tool_input":{"file_path":"pyproject.toml","content":"starlette = \"1.0.0\""}}'
assert_block "pyproject exact 1.0.0 -> block" "CVE-2026-48710"

# ============================================================
# poetry.lock / uv.lock — [[package]] blocks
# ============================================================

run '{"tool_input":{"file_path":"poetry.lock","content":"[[package]]\nname = \"jinja2\"\nversion = \"3.1.3\"\ndescription = \"x\"\n"}}'
assert_block "poetry.lock jinja2 3.1.3 -> block" "CVE-2024-34064"

run '{"tool_input":{"file_path":"poetry.lock","content":"[[package]]\nname = \"jinja2\"\nversion = \"3.1.4\"\n"}}'
assert_exit "poetry.lock jinja2 3.1.4 (== fix) -> allow" 0

run '{"tool_input":{"file_path":"uv.lock","content":"[[package]]\nname = \"aiohttp\"\nversion = \"3.9.1\"\n"}}'
assert_block "uv.lock aiohttp 3.9.1 -> block" "CVE-2024-23334"

# ============================================================
# Edit / MultiEdit tool shapes
# ============================================================

run '{"tool_input":{"file_path":"requirements.txt","old_string":"starlette","new_string":"starlette==1.0.0"}}'
assert_block "Edit new_string pins starlette==1.0.0 -> block" "CVE-2026-48710"

run '{"tool_input":{"file_path":"requirements.txt","edits":[{"old_string":"a","new_string":"x"},{"old_string":"b","new_string":"urllib3==2.2.1"}]}}'
assert_block "MultiEdit edits[].new_string pins urllib3 -> block" "CVE-2024-37891"

# ============================================================
# Skip-safe / malformed
# ============================================================

run '{"tool_input":{"file_path":"requirements.txt","content":""}}'
assert_exit "empty content -> allow" 0

run ''
assert_exit "empty stdin -> allow" 0

run 'not-json'
assert_exit "non-JSON stdin -> allow" 0

run '{"tool_input":{"file_path":"README.md","content":"starlette==1.0.0 is vulnerable"}}'
assert_block "prose mentioning a pin still matches the pin -> block" "CVE-2026-48710"

# ============================================================
# Report
# ============================================================

printf '\n============================================================\n'
printf 'PASS: %s\n' "$PASS"
printf 'FAIL: %s\n' "$FAIL"
if [ "$FAIL" -gt 0 ]; then
    printf '%s\n' "$DETAILS"
    exit 1
fi
printf '\nAll tests green.\n'
