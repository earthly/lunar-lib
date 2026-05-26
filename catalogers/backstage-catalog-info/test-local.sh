#!/bin/bash
#
# Local offline test for the backstage-catalog-info cataloger.
#
# Mocks `lunar component get-json <id>` to return each scenario from
# test/fixtures.json, and mocks `lunar catalog raw --json '.components' -`
# to capture writes to a file. Then asserts the captured output matches
# the expected Catalog JSON entry for that scenario.
#
# All scenarios run; any failure is logged with a diff and the script
# exits non-zero at the end.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR=$(mktemp -d)
FIXTURES="$SCRIPT_DIR/test/fixtures.json"

trap 'rm -rf "$TEST_DIR"' EXIT

echo "Test directory: $TEST_DIR"
echo "Fixtures:       $FIXTURES"
echo ""

# --- Mock lunar -----------------------------------------------------------
# Two subcommands handled:
#   lunar component get-json <id>          → reads $TEST_DIR/component.json
#   lunar catalog raw --json '.components' - → appends stdin to
#                                              $TEST_DIR/components.out
cat > "$TEST_DIR/lunar" << 'EOF'
#!/bin/bash
set -euo pipefail
TEST_DIR_ENV="${MOCK_LUNAR_TEST_DIR:?MOCK_LUNAR_TEST_DIR must be set}"
case "${1:-}" in
    component)
        if [ "${2:-}" = "get-json" ]; then
            cat "$TEST_DIR_ENV/component.json"
            exit 0
        fi
        echo "Mock lunar: unhandled component subcommand: ${2:-}" >&2
        exit 1
        ;;
    catalog)
        if [ "${2:-}" = "raw" ] && [ "${3:-}" = "--json" ]; then
            case "${4:-}" in
                .components)
                    cat >> "$TEST_DIR_ENV/components.out"
                    echo "" >> "$TEST_DIR_ENV/components.out"
                    exit 0
                    ;;
            esac
            echo "Mock lunar: unhandled catalog path: ${4:-}" >&2
            exit 1
        fi
        echo "Mock lunar: unhandled catalog subcommand" >&2
        exit 1
        ;;
esac
echo "Mock lunar: unhandled command: $*" >&2
exit 1
EOF
chmod +x "$TEST_DIR/lunar"

export PATH="$TEST_DIR:$PATH"
export MOCK_LUNAR_TEST_DIR="$TEST_DIR"

# --- Test runner ----------------------------------------------------------
# run_scenario <name> <component-id> <expected-jq-on-merged-output>
# Where <expected-jq-on-merged-output> is a jq filter that should produce
# "true" against the merged components.out content. "" means expect no
# write (skipped scenario).
FAILED=0
PASSED=0

run_scenario() {
    local name="$1"
    local component_id="$2"
    local expected_jq="$3"
    shift 3
    # remaining args are LUNAR_VAR_* overrides as KEY=VALUE

    echo "── scenario: $name ──"

    # Fresh capture file
    : > "$TEST_DIR/components.out"

    # Materialize the fixture's component JSON (strip _comment/_component_id metadata)
    jq --arg key "$name" '.[$key] | del(._comment, ._component_id)' "$FIXTURES" > "$TEST_DIR/component.json"

    # Reset env to defaults for each scenario
    unset LUNAR_VAR_COMPONENT_ID_ANNOTATION LUNAR_VAR_COMPONENT_ID_PREFIX
    unset LUNAR_VAR_TAG_PREFIX LUNAR_VAR_INCLUDE_DERIVED_TAGS
    unset LUNAR_VAR_OWNER_FORMAT LUNAR_VAR_DEFAULT_OWNER

    for kv in "$@"; do
        export "$kv"
    done

    export LUNAR_COMPONENT_ID="$component_id"

    # Run the cataloger; capture stdout+stderr for the log but don't fail the
    # whole script on a non-zero exit — we'll report per-scenario.
    local log
    log=$("$SCRIPT_DIR/main.sh" 2>&1) || {
        echo "  main.sh exited non-zero — FAIL"
        echo "$log" | sed 's/^/    /'
        FAILED=$((FAILED + 1))
        return
    }

    # Merge what got written (file may be empty for skips). Each batch is a
    # single JSON object on its own; merge them into one.
    local merged
    if [ -s "$TEST_DIR/components.out" ]; then
        merged=$(jq -s 'add // {}' "$TEST_DIR/components.out" 2>/dev/null || echo '{}')
    else
        merged='{}'
    fi

    if [ -z "$expected_jq" ]; then
        # Expect no write
        if [ "$merged" = "{}" ]; then
            echo "  OK (correctly skipped — no write)"
            PASSED=$((PASSED + 1))
        else
            echo "  FAIL (expected no write, got):"
            echo "$merged" | jq . | sed 's/^/    /'
            FAILED=$((FAILED + 1))
        fi
        return
    fi

    local check
    check=$(echo "$merged" | jq -r "$expected_jq" 2>&1 || echo "JQ_ERROR")
    if [ "$check" = "true" ]; then
        echo "  OK"
        echo "$merged" | jq . | sed 's/^/    /'
        PASSED=$((PASSED + 1))
    else
        echo "  FAIL — assertion did not pass (got: $check)"
        echo "  merged output:"
        echo "$merged" | jq . | sed 's/^/    /'
        echo "  jq filter: $expected_jq"
        FAILED=$((FAILED + 1))
    fi
}

# ── Scenario 1: annotation match, defaults ────────────────────────────────
# Expect owner verbatim, domain from spec.domain, tags = prefixed metadata + derived
run_scenario "annotation_match" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"] | (.owner == "group:default/team-payments" and .domain == "platform.payments" and (.tags | sort) == (["bs-payments","bs-tier1","bs-type-service","bs-lifecycle-production"] | sort))'

# ── Scenario 2: ID fallback (no annotation on entity) ─────────────────────
# Expect match via prefix; domain falls back to bare(spec.system) = "storefront"
run_scenario "id_fallback" "github.com/acme/web-app" \
    '.["github.com/acme/web-app"] | (.owner == "group:default/team-web" and .domain == "storefront" and (.tags | sort) == (["bs-frontend","bs-type-website","bs-lifecycle-production"] | sort))'

# ── Scenario 3: owner_format=bare-name ────────────────────────────────────
run_scenario "owner_format_bare" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"].owner == "team-payments"' \
    LUNAR_VAR_OWNER_FORMAT=bare-name

# ── Scenario 4: default_owner fallback ────────────────────────────────────
run_scenario "default_owner_fallback" "github.com/acme/orphan" \
    '.["github.com/acme/orphan"].owner == "fallback-team"' \
    LUNAR_VAR_DEFAULT_OWNER=fallback-team

# ── Scenario 5: include_derived_tags=false drops type-*/lifecycle-* ───────
run_scenario "no_derived_tags" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"].tags == ["bs-payments"]' \
    LUNAR_VAR_INCLUDE_DERIVED_TAGS=false

# ── Skip scenarios (expect no write) ──────────────────────────────────────
run_scenario "skip_missing_data" "github.com/acme/no-collector-yet" ""
run_scenario "skip_invalid" "github.com/acme/payment-api" ""
run_scenario "skip_wrong_kind" "github.com/acme/payment-api" ""
run_scenario "skip_annotation_mismatch" "github.com/acme/payment-api" ""
run_scenario "skip_no_annotation_and_prefix_mismatch" "gitlab.com/acme/payment-api" ""

# ── Summary ───────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Passed: $PASSED  Failed: $FAILED"
echo "=========================================="
if [ "$FAILED" -gt 0 ]; then
    exit 1
fi
