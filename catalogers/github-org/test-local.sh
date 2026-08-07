#!/bin/bash
#
# Local test for the github-org cataloger.
#
# By default runs OFFLINE, deterministic scenarios: mocks `gh repo list ...` to
# return a fixed repo fixture and `lunar catalog raw --json ...` to capture
# writes, then asserts the resulting tags for a range of tag_prefix values —
# including the empty-prefix regression guard (ENG-1106): an explicit empty
# `tag_prefix` must yield un-prefixed topics.
#
# All scenarios run; any failure is logged and the script exits non-zero.
#
# Opt-in real-API smoke: RUN_REAL_API_SMOKE=1 ./test-local.sh runs main.sh once
# against a real org (TEST_ORG, default "earthly") using the real gh CLI, and
# prints the captured catalog (no assertions — real topics vary). Requires a
# gh token (LUNAR_SECRET_GH_TOKEN / GH_TOKEN, or `gh auth token`).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR=$(mktemp -d)
COMPONENTS_OUT="$TEST_DIR/components.out"
DOMAINS_OUT="$TEST_DIR/domains.out"
REPOS_FIXTURE="$TEST_DIR/repos.json"

# Resolve the real gh before shadowing it on PATH (used by the opt-in smoke).
REAL_GH="$(command -v gh || true)"

trap 'rm -rf "$TEST_DIR"' EXIT

echo "Test directory: $TEST_DIR"
echo ""

# --- Mock gh --------------------------------------------------------------
# For `gh repo list <org> --visibility <v> ... --json ... [--no-archived]`,
# emit the fixture at $MOCK_GH_REPOS_FILE for the "public" visibility (an empty
# array for any other visibility). If no fixture is configured, delegate to the
# real gh — that's how the opt-in real-API smoke reuses this same PATH shim.
cat > "$TEST_DIR/gh" << 'EOF'
#!/bin/bash
set -euo pipefail
if [ -z "${MOCK_GH_REPOS_FILE:-}" ]; then
    exec "${REAL_GH:?real gh not found on PATH}" "$@"
fi
if [ "${1:-}" = "repo" ] && [ "${2:-}" = "list" ]; then
    visibility=""
    while [ $# -gt 0 ]; do
        [ "$1" = "--visibility" ] && visibility="${2:-}"
        shift
    done
    if [ "$visibility" = "public" ]; then
        cat "$MOCK_GH_REPOS_FILE"
    else
        echo "[]"
    fi
    exit 0
fi
echo "Mock gh: unhandled command: $*" >&2
exit 1
EOF
chmod +x "$TEST_DIR/gh"

# --- Mock lunar -----------------------------------------------------------
# Handles `lunar catalog raw --json '<path>' -` for `.components` and
# `.domains`, appending each write to a per-path .out file so a scenario can be
# asserted against the merged result.
cat > "$TEST_DIR/lunar" << 'EOF'
#!/bin/bash
set -euo pipefail
if [ "${1:-}" = "catalog" ] && [ "${2:-}" = "raw" ] && [ "${3:-}" = "--json" ]; then
    case "${4:-}" in
        .components)
            cat >> "$MOCK_LUNAR_COMPONENTS_OUT"; echo "" >> "$MOCK_LUNAR_COMPONENTS_OUT"; exit 0 ;;
        .domains)
            cat >> "$MOCK_LUNAR_DOMAINS_OUT"; echo "" >> "$MOCK_LUNAR_DOMAINS_OUT"; exit 0 ;;
    esac
fi
echo "Mock lunar: unhandled command: $*" >&2
exit 1
EOF
chmod +x "$TEST_DIR/lunar"

export PATH="$TEST_DIR:$PATH"
export REAL_GH
export MOCK_LUNAR_COMPONENTS_OUT="$COMPONENTS_OUT"
export MOCK_LUNAR_DOMAINS_OUT="$DOMAINS_OUT"

# --- Repo fixture ---------------------------------------------------------
# Two public repos with topics; the "payment-api" tags are what the scenarios
# assert against (topic → tag with/without prefix).
cat > "$REPOS_FIXTURE" << 'EOF'
[
  {
    "name": "payment-api",
    "url": "https://github.com/acme/payment-api",
    "description": "Payment processing API",
    "repositoryTopics": [{"name": "backend"}, {"name": "go"}],
    "isArchived": false,
    "visibility": "public"
  },
  {
    "name": "frontend-app",
    "url": "https://github.com/acme/frontend-app",
    "description": "Customer-facing web app",
    "repositoryTopics": [{"name": "react"}],
    "isArchived": false,
    "visibility": "public"
  }
]
EOF

# Shared inputs for the offline scenarios: one org, public only (single gh
# call), no filters/owner/domain. Each scenario sets LUNAR_VAR_TAG_PREFIX.
export MOCK_GH_REPOS_FILE="$REPOS_FIXTURE"
export LUNAR_SECRET_GH_TOKEN="dummy-token"   # main.sh requires a token to be set
export LUNAR_VAR_ORG_NAME="acme"
export LUNAR_VAR_INCLUDE_PUBLIC="true"
export LUNAR_VAR_INCLUDE_PRIVATE="false"
export LUNAR_VAR_INCLUDE_INTERNAL="false"
export LUNAR_VAR_INCLUDE_ARCHIVED="false"
export LUNAR_VAR_INCLUDE_REPOS=""
export LUNAR_VAR_EXCLUDE_REPOS=""
export LUNAR_VAR_DEFAULT_OWNER=""
export LUNAR_VAR_DEFAULT_DOMAIN=""
export LUNAR_VAR_GITHUB_HOST="github.com"

# --- Test runner ----------------------------------------------------------
# run_scenario <name> <expected-jq-on-merged-components>
# The caller sets LUNAR_VAR_TAG_PREFIX (or unsets it) before calling.
FAILED=0
PASSED=0

run_scenario() {
    local name="$1"
    local expected_jq="$2"

    echo "── scenario: $name ──"
    : > "$COMPONENTS_OUT"
    : > "$DOMAINS_OUT"

    if ! "$SCRIPT_DIR/main.sh" > "$TEST_DIR/$name.log" 2>&1; then
        echo "  FAIL: main.sh exited non-zero"
        sed 's/^/    /' "$TEST_DIR/$name.log"
        FAILED=$((FAILED + 1))
        return
    fi

    local merged
    merged=$(jq -s 'add' "$COMPONENTS_OUT")

    if [ "$(echo "$merged" | jq "$expected_jq")" = "true" ]; then
        echo "  PASS"
        PASSED=$((PASSED + 1))
    else
        echo "  FAIL: assertion did not hold: $expected_jq"
        echo "  merged components:"
        echo "$merged" | jq '.' | sed 's/^/    /'
        FAILED=$((FAILED + 1))
    fi
}

PA='.["github.com/acme/payment-api"].tags | sort'

# Default prefix: topics come out "gh-<topic>", visibility tag un-prefixed.
export LUNAR_VAR_TAG_PREFIX="gh-"
run_scenario "default_prefix" \
    "($PA) == ([\"gh-backend\",\"gh-go\",\"github-visibility-public\"] | sort)"

# Custom prefix: honored verbatim.
export LUNAR_VAR_TAG_PREFIX="topic-"
run_scenario "custom_prefix" \
    "($PA) == ([\"topic-backend\",\"topic-go\",\"github-visibility-public\"] | sort)"

# ── ENG-1106 regression: tag_prefix="" disables prefixing entirely ────────
# An explicit empty tag_prefix must pass topics through un-prefixed, per the
# documented "empty string disables the prefix" contract. Guard: the old
# `${LUNAR_VAR_TAG_PREFIX:-gh-}` clobbered a config-supplied empty value back
# to "gh-", so this scenario failed (topics came out "gh-*").
export LUNAR_VAR_TAG_PREFIX=""
run_scenario "tag_prefix_disabled" \
    "($PA) == ([\"backend\",\"go\",\"github-visibility-public\"] | sort)"

# Truly-unset var (direct local invocation) still defaults to "gh-" — the `-`
# fallback only fires when the variable is absent, not when it's empty.
unset LUNAR_VAR_TAG_PREFIX
run_scenario "unset_prefix_defaults_to_gh" \
    "($PA) == ([\"gh-backend\",\"gh-go\",\"github-visibility-public\"] | sort)"

# ── Topic allowlist: only repos carrying an allowed topic are cataloged ───
# payment-api has topics backend/go; frontend-app has react. allow=go keeps
# payment-api, drops frontend-app.
export LUNAR_VAR_TAG_PREFIX="gh-"
export LUNAR_VAR_ALLOWED_TOPICS="go"
run_scenario "allowed_topics" \
    '(has("github.com/acme/payment-api")) and (has("github.com/acme/frontend-app") | not)'
unset LUNAR_VAR_ALLOWED_TOPICS

# ── Topic blocklist: a repo carrying a disallowed topic is excluded ───────
export LUNAR_VAR_DISALLOWED_TOPICS="react"
run_scenario "disallowed_topics" \
    '(has("github.com/acme/payment-api")) and (has("github.com/acme/frontend-app") | not)'
unset LUNAR_VAR_DISALLOWED_TOPICS

# ── Block wins over allow when a repo matches both lists ──────────────────
# allow=go,react matches both repos; disallow=go then removes payment-api.
export LUNAR_VAR_ALLOWED_TOPICS="go,react"
export LUNAR_VAR_DISALLOWED_TOPICS="go"
run_scenario "disallow_beats_allow" \
    '(has("github.com/acme/payment-api") | not) and (has("github.com/acme/frontend-app"))'
unset LUNAR_VAR_ALLOWED_TOPICS LUNAR_VAR_DISALLOWED_TOPICS

echo ""
echo "Offline scenarios: $PASSED passed, $FAILED failed"

# --- Opt-in real-API smoke ------------------------------------------------
if [ "${RUN_REAL_API_SMOKE:-}" = "1" ]; then
    echo ""
    echo "=== Real-API smoke (RUN_REAL_API_SMOKE=1) ==="
    if [ -z "$REAL_GH" ]; then
        echo "  SKIP: gh CLI not found on PATH"
    else
        unset MOCK_GH_REPOS_FILE   # delegate the mock gh to the real gh
        : > "$COMPONENTS_OUT"; : > "$DOMAINS_OUT"
        SMOKE_TOKEN="${LUNAR_SECRET_GH_TOKEN:-${GH_TOKEN:-}}"
        [ "$SMOKE_TOKEN" = "dummy-token" ] && SMOKE_TOKEN=""
        [ -z "$SMOKE_TOKEN" ] && SMOKE_TOKEN="$("$REAL_GH" auth token 2>/dev/null || true)"
        if [ -z "$SMOKE_TOKEN" ]; then
            echo "  SKIP: no token (set LUNAR_SECRET_GH_TOKEN / GH_TOKEN or run 'gh auth login')"
        else
            LUNAR_SECRET_GH_TOKEN="$SMOKE_TOKEN" \
            LUNAR_VAR_ORG_NAME="${TEST_ORG:-earthly}" \
            LUNAR_VAR_INCLUDE_PRIVATE="false" \
            LUNAR_VAR_INCLUDE_INTERNAL="false" \
            LUNAR_VAR_TAG_PREFIX="gh-" \
                "$SCRIPT_DIR/main.sh" || echo "  main.sh exited non-zero"
            echo "  --- captured components ---"
            jq -s 'add' "$COMPONENTS_OUT" 2>/dev/null | sed 's/^/  /' || echo "  (none)"
        fi
    fi
fi

if [ "$FAILED" -ne 0 ]; then
    exit 1
fi
