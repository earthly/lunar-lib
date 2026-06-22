#!/bin/sh
# test/run_tests.sh — lightweight test harness for check-pr-title.sh.
#
# Each test boots a throwaway git repo on a controllable branch, pipes
# a PreToolUse JSON payload through the check, then asserts on exit
# code + stdout.
#
# shellcheck disable=SC2016
# The payload strings are single-quoted on purpose: the `$(...)` and
# backtick sequences inside them are literal test data (we assert the
# check *defers* on command substitution), not expansions.

set -u

SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/scripts/check-pr-title.sh"
PASS=0
FAIL=0
FAIL_DETAILS=""
RESULT_EXIT=""
RESULT_STDOUT=""

run_check() {
    # $1 = branch name
    # $2 = JSON payload (stdin)
    # $3 = LUNAR_VAR_PATTERN override (empty = unset)
    # $4 = LUNAR_VAR_ENFORCE_DRAFTS override (empty = unset)
    branch="$1"
    payload="$2"
    pattern_env="$3"
    enforce_drafts_env="${4:-}"

    tmp="$(mktemp -d)"
    (
        cd "$tmp" || exit
        git init -q
        git config user.email t@t.t
        git config user.name t
        git commit --allow-empty -q -m init
        git checkout -q -b "$branch" 2>/dev/null
    ) >/dev/null 2>&1

    set --
    [ -n "$pattern_env" ]        && set -- "$@" "LUNAR_VAR_PATTERN=$pattern_env"
    [ -n "$enforce_drafts_env" ] && set -- "$@" "LUNAR_VAR_ENFORCE_DRAFTS=$enforce_drafts_env"

    RESULT_STDOUT="$(cd "$tmp" && printf '%s' "$payload" | env "$@" sh "$SCRIPT" 2>/dev/null)"
    RESULT_EXIT=$?

    rm -rf "$tmp"
}

assert() {
    # $1 = case name
    # $2 = expected exit code
    # $3 = expected stdout (empty = don't check stdout)
    name="$1"
    expected_exit="$2"
    expected_stdout="$3"

    if [ "$RESULT_EXIT" != "$expected_exit" ]; then
        FAIL=$((FAIL + 1))
        FAIL_DETAILS="${FAIL_DETAILS}
  [FAIL] $name
         expected exit=$expected_exit stdout=<$expected_stdout>
         got      exit=$RESULT_EXIT stdout=<$RESULT_STDOUT>"
        return
    fi
    if [ -n "$expected_stdout" ] && [ "$RESULT_STDOUT" != "$expected_stdout" ]; then
        FAIL=$((FAIL + 1))
        FAIL_DETAILS="${FAIL_DETAILS}
  [FAIL] $name
         expected stdout=<$expected_stdout>
         got      stdout=<$RESULT_STDOUT>"
        return
    fi
    PASS=$((PASS + 1))
}

# ============================================================
# Happy path
# ============================================================

run_check "main" '{"tool_input":{"command":"gh pr create --title \"[ENG-800] Add probe\""}}' ""
assert "block: ticket present → allow" 0 ""

run_check "main" '{"tool_input":{"command":"gh pr create --title \"feat: ENG-99 add bar\" --body foo"}}' ""
assert "ticket mid-title → allow" 0 ""

run_check "main" '{"tool_input":{"command":"gh pr create --title \"[ABC-1] tiny\""}}' ""
assert "minimal ticket [ABC-1] → allow" 0 ""

# ============================================================
# Block: no ticket
# ============================================================

run_check "main" '{"tool_input":{"command":"gh pr create --title \"Add probe\""}}' ""
assert "no ticket → block (title echoed)" 1 "Add probe"

run_check "main" '{"tool_input":{"command":"gh pr create --title=\"Refactor stuff\""}}' ""
assert "--title=value, no ticket → block" 1 "Refactor stuff"

run_check "main" '{"tool_input":{"command":"gh pr create --title \"eng-800 lowercase\""}}' ""
assert "lowercase eng (uppercase required by default) → block" 1 "eng-800 lowercase"

# ============================================================
# Skip: draft
# ============================================================

run_check "main" '{"tool_input":{"command":"gh pr create --draft --title \"Add probe\""}}' ""
assert "--draft → allow" 0 ""

run_check "main" '{"tool_input":{"command":"gh pr create -d --title \"Add probe\""}}' ""
assert "-d short → allow" 0 ""

# ============================================================
# Skip: bot branches
# ============================================================

run_check "dependabot/npm/foo" '{"tool_input":{"command":"gh pr create --title \"Bump foo\""}}' ""
assert "dependabot/* branch → allow" 0 ""

run_check "renovate/all" '{"tool_input":{"command":"gh pr create --title \"Update deps\""}}' ""
assert "renovate/* branch → allow" 0 ""

# ============================================================
# Skip: NO-TICKET: prefix
# ============================================================

run_check "main" '{"tool_input":{"command":"gh pr create --title \"NO-TICKET: fix typo\""}}' ""
assert "NO-TICKET: prefix → allow" 0 ""

run_check "main" '{"tool_input":{"command":"gh pr create --title \"no-ticket: fix typo\""}}' ""
assert "no-ticket: lowercase prefix → allow" 0 ""

run_check "main" '{"tool_input":{"command":"gh pr create --title \"No-Ticket: README\""}}' ""
assert "No-Ticket: mixed-case prefix → allow" 0 ""

# ============================================================
# Skip: not gh pr create
# ============================================================

run_check "main" '{"tool_input":{"command":"gh pr view 123"}}' ""
assert "gh pr view → allow" 0 ""

run_check "main" '{"tool_input":{"command":"gh issue create --title foo"}}' ""
assert "gh issue create → allow" 0 ""

run_check "main" '{"tool_input":{"command":"gh pr edit 1 --title foo"}}' ""
assert "gh pr edit → allow" 0 ""

run_check "main" '{"tool_input":{"command":"git status"}}' ""
assert "git command → allow" 0 ""

# ============================================================
# Skip: no title parsed (defer to gh)
# ============================================================

run_check "main" '{"tool_input":{"command":"gh pr create --body foo"}}' ""
assert "no --title flag → allow (defer to gh)" 0 ""

run_check "main" '{"tool_input":{"command":"gh pr create"}}' ""
assert "no flags at all → allow (defer to gh)" 0 ""

# ============================================================
# Skip: command substitution / dangerous syntax (defer to gh)
# ============================================================

run_check "main" '{"tool_input":{"command":"gh pr create --title \"$(date)\""}}' ""
assert 'dollar-paren substitution → allow (safe defer)' 0 ""

run_check "main" '{"tool_input":{"command":"gh pr create --title \"`date`\""}}' ""
assert 'backtick substitution → allow (safe defer)' 0 ""

# ============================================================
# Edge: empty / malformed payload
# ============================================================

run_check "main" '' ""
assert "empty stdin → allow" 0 ""

run_check "main" '{"tool_input":{"command":""}}' ""
assert "empty command → allow" 0 ""

run_check "main" 'not-json' ""
assert "non-JSON stdin → allow" 0 ""

# ============================================================
# Edge: --title flag variants
# ============================================================

run_check "main" '{"tool_input":{"command":"gh pr create -t \"[ENG-800] foo\""}}' ""
assert "-t with value → allow" 0 ""

run_check "main" '{"tool_input":{"command":"gh pr create -t \"missing ticket\""}}' ""
assert "-t with bad title → block" 1 "missing ticket"

# ============================================================
# Configurable pattern (forward-compat, when input dispatch ships)
# ============================================================

run_check "main" '{"tool_input":{"command":"gh pr create --title \"[OPS-100] foo\""}}' '^\[(ENG|OPS)-[0-9]+\]'
assert "custom ^[(ENG|OPS)-N] + OPS-100 → allow" 0 ""

run_check "main" '{"tool_input":{"command":"gh pr create --title \"[BLA-100] foo\""}}' '^\[(ENG|OPS)-[0-9]+\]'
assert "custom ^[(ENG|OPS)-N] + BLA-100 → block" 1 "[BLA-100] foo"

run_check "main" '{"tool_input":{"command":"gh pr create --title \"ENG-7\""}}' '[A-Z]+-\d+'
assert "custom pattern w/ PCRE \\d → allow (translated to [0-9])" 0 ""

# ============================================================
# Configurable enforce_drafts (forward-compat, when input dispatch ships)
# ============================================================

run_check "main" '{"tool_input":{"command":"gh pr create --draft --title \"Add probe\""}}' "" "true"
assert "enforce_drafts=true + --draft + no ticket → block" 1 "Add probe"

run_check "main" '{"tool_input":{"command":"gh pr create -d --title \"Add probe\""}}' "" "true"
assert "enforce_drafts=true + -d + no ticket → block" 1 "Add probe"

run_check "main" '{"tool_input":{"command":"gh pr create --draft --title \"[ENG-800] Add probe\""}}' "" "true"
assert "enforce_drafts=true + --draft + ticket present → allow" 0 ""

run_check "main" '{"tool_input":{"command":"gh pr create --draft --title \"Add probe\""}}' "" "1"
assert "enforce_drafts=1 (truthy) + --draft + no ticket → block" 1 "Add probe"

run_check "main" '{"tool_input":{"command":"gh pr create --draft --title \"Add probe\""}}' "" "TRUE"
assert "enforce_drafts=TRUE (case-insensitive) + --draft + no ticket → block" 1 "Add probe"

run_check "main" '{"tool_input":{"command":"gh pr create --draft --title \"Add probe\""}}' "" "false"
assert "enforce_drafts=false (explicit) + --draft + no ticket → allow" 0 ""

run_check "main" '{"tool_input":{"command":"gh pr create --draft --title \"Add probe\""}}' "" "no"
assert "enforce_drafts=no (other falsy) + --draft + no ticket → allow" 0 ""

run_check "main" '{"tool_input":{"command":"gh pr create --draft --title \"NO-TICKET: fix typo\""}}' "" "true"
assert "enforce_drafts=true + --draft + NO-TICKET prefix → allow (allowlist wins)" 0 ""

run_check "dependabot/npm/foo" '{"tool_input":{"command":"gh pr create --draft --title \"Bump foo\""}}' "" "true"
assert "enforce_drafts=true + --draft + dependabot/* branch → allow (bot skip wins)" 0 ""

# ============================================================
# Wrapper entrypoint: `*-pr-create` (a script that forwards the same
# --title flags to `gh pr create`). The agent invokes the wrapper, so
# the hook never sees the inner `gh` — the check must match on the
# wrapper name and parse its argv as gh-pr-create-style flags.
# ============================================================

run_check "main" '{"tool_input":{"command":"acme-pr-create --title \"[ENG-800] Add probe\""}}' ""
assert "wrapper: ticket present → allow" 0 ""

run_check "main" '{"tool_input":{"command":"acme-pr-create --title \"Add probe\""}}' ""
assert "wrapper: no ticket → block (title echoed)" 1 "Add probe"

run_check "main" '{"tool_input":{"command":"acme-pr-create --title=\"Refactor stuff\""}}' ""
assert "wrapper: --title=value, no ticket → block" 1 "Refactor stuff"

run_check "main" '{"tool_input":{"command":"acme-pr-create -t \"[ABC-1] tiny\""}}' ""
assert "wrapper: -t with ticket → allow" 0 ""

# A wrapper's own long flags must fall through harmlessly to the title parse.
run_check "main" '{"tool_input":{"command":"acme-pr-create --wrapper-only-flag --title \"missing ticket\""}}' ""
assert "wrapper: own flag + bad title → block" 1 "missing ticket"

# Invoked via absolute path — the check basenames the entrypoint token.
run_check "main" '{"tool_input":{"command":"/usr/local/bin/acme-pr-create --title \"missing ticket\""}}' ""
assert "wrapper: absolute path + bad title → block" 1 "missing ticket"

# Skip rules apply identically to wrappers.
run_check "main" '{"tool_input":{"command":"acme-pr-create --draft --title \"Add probe\""}}' ""
assert "wrapper: --draft + no ticket → allow (draft skip default)" 0 ""

run_check "main" '{"tool_input":{"command":"acme-pr-create --draft --title \"Add probe\""}}' "" "true"
assert "wrapper: enforce_drafts=true + --draft + no ticket → block" 1 "Add probe"

run_check "main" '{"tool_input":{"command":"acme-pr-create --title \"NO-TICKET: chore\""}}' ""
assert "wrapper: NO-TICKET: prefix → allow" 0 ""

run_check "renovate/all" '{"tool_input":{"command":"acme-pr-create --title \"Update deps\""}}' ""
assert "wrapper: renovate/* branch → allow (bot skip)" 0 ""

run_check "main" '{"tool_input":{"command":"acme-pr-create --title \"[ENG-$(num)] foo\""}}' ""
assert "wrapper: command substitution → allow (safe defer)" 0 ""

# A command that is neither `gh` nor a `*-pr-create` wrapper must be left
# alone even if the check is somehow invoked directly (the hook matcher is
# the first gate, this is the script's own belt-and-suspenders).
run_check "main" '{"tool_input":{"command":"create-pr --title \"missing ticket\""}}' ""
assert "non-gh non-wrapper command → allow (defer)" 0 ""

# ============================================================
# Report
# ============================================================

printf '\n============================================================\n'
printf 'PASS: %s\n' "$PASS"
printf 'FAIL: %s\n' "$FAIL"
if [ "$FAIL" -gt 0 ]; then
    printf '%s\n' "$FAIL_DETAILS"
    exit 1
fi
printf '\nAll tests green.\n'
