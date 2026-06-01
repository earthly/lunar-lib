#!/bin/bash
#
# Local offline test for the backstage-catalog-info cataloger.
#
# Mocks `gh api -H "Accept: application/vnd.github.raw" repos/.../contents/...`
# to return per-scenario fixtures from test/fixtures/<name>.yaml (absence
# simulates a 404), and mocks `lunar catalog raw --json '.components' -` to
# capture writes to a file. Then asserts the captured output matches the
# expected Catalog JSON entry for that scenario.
#
# All scenarios run; any failure is logged with a diff and the script
# exits non-zero at the end.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR=$(mktemp -d)
FIXTURES_DIR="$SCRIPT_DIR/test/fixtures"

trap 'rm -rf "$TEST_DIR"' EXIT

echo "Test directory: $TEST_DIR"
echo "Fixtures dir:   $FIXTURES_DIR"
echo ""

# --- Mock gh --------------------------------------------------------------
# Only handles `gh api ... repos/<slug>/contents/<path>` style calls. Reads
# $TEST_DIR/fetched.yaml. If the file is absent, exits 1 (simulating 404).
cat > "$TEST_DIR/gh" << 'EOF'
#!/bin/bash
set -euo pipefail
TEST_DIR_ENV="${MOCK_GH_TEST_DIR:?MOCK_GH_TEST_DIR must be set}"
seen_api=0
for arg in "$@"; do
    if [ "$arg" = "api" ]; then
        seen_api=1
        break
    fi
done
if [ "$seen_api" -eq 0 ]; then
    echo "Mock gh: only 'gh api ...' is supported, got: $*" >&2
    exit 1
fi
if [ -f "$TEST_DIR_ENV/fetched.yaml" ]; then
    cat "$TEST_DIR_ENV/fetched.yaml"
    exit 0
fi
echo '{"message":"Not Found"}' >&2
exit 1
EOF
chmod +x "$TEST_DIR/gh"

# --- Mock lunar -----------------------------------------------------------
# Only `lunar catalog raw --json '.components' -` is needed: it appends stdin
# to $TEST_DIR/components.out.
cat > "$TEST_DIR/lunar" << 'EOF'
#!/bin/bash
set -euo pipefail
TEST_DIR_ENV="${MOCK_LUNAR_TEST_DIR:?MOCK_LUNAR_TEST_DIR must be set}"
if [ "${1:-}" = "catalog" ] && [ "${2:-}" = "raw" ] && [ "${3:-}" = "--json" ] && [ "${4:-}" = ".components" ]; then
    cat >> "$TEST_DIR_ENV/components.out"
    echo "" >> "$TEST_DIR_ENV/components.out"
    exit 0
fi
echo "Mock lunar: unhandled command: $*" >&2
exit 1
EOF
chmod +x "$TEST_DIR/lunar"

export PATH="$TEST_DIR:$PATH"
export MOCK_GH_TEST_DIR="$TEST_DIR"
export MOCK_LUNAR_TEST_DIR="$TEST_DIR"

# --- Test runner ----------------------------------------------------------
# run_scenario <name> <fixture-or-NONE> <component-id> <expected-jq> [env-overrides...]
# fixture-or-NONE: basename under test/fixtures/, or NONE to simulate 404
# expected-jq: jq filter on merged components.out; "true" means pass.
#              "" means expect no write (skipped scenario)
FAILED=0
PASSED=0

run_scenario() {
    local name="$1"
    local fixture="$2"
    local component_id="$3"
    local expected_jq="$4"
    shift 4

    echo "── scenario: $name ──"

    # Fresh state per scenario
    : > "$TEST_DIR/components.out"
    rm -f "$TEST_DIR/fetched.yaml"

    if [ "$fixture" != "NONE" ]; then
        cp "$FIXTURES_DIR/$fixture.yaml" "$TEST_DIR/fetched.yaml"
    fi

    # Reset env to defaults for each scenario
    unset LUNAR_VAR_COMPONENT_ID_ANNOTATION LUNAR_VAR_COMPONENT_ID_PREFIX
    unset LUNAR_VAR_TAG_PREFIX LUNAR_VAR_INCLUDE_DERIVED_TAGS
    unset LUNAR_VAR_OWNER_FORMAT LUNAR_VAR_DEFAULT_OWNER
    unset LUNAR_VAR_PATHS LUNAR_VAR_BRANCH

    for kv in "$@"; do
        export "$kv"
    done

    export LUNAR_COMPONENT_ID="$component_id"
    export LUNAR_SECRET_GH_TOKEN="test-token-stub"

    local log
    log=$("$SCRIPT_DIR/main.sh" 2>&1) || {
        echo "  main.sh exited non-zero — FAIL"
        echo "$log" | sed 's/^/    /'
        FAILED=$((FAILED + 1))
        return
    }

    local merged
    if [ -s "$TEST_DIR/components.out" ]; then
        merged=$(jq -s 'add // {}' "$TEST_DIR/components.out" 2>/dev/null || echo '{}')
    else
        merged='{}'
    fi

    if [ -z "$expected_jq" ]; then
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

# ── Scenario: annotation match, defaults ──────────────────────────────────
run_scenario "annotation_match" "annotation_match" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"] | (.owner == "group:default/team-payments" and .domain == "platform.payments" and (.tags | sort) == (["bs-payments","bs-tier1","bs-type-service","bs-lifecycle-production"] | sort))'

# ── Scenario: single-Component-no-annotation fallback ─────────────────────
# Component has no project-slug annotation, but it's the only Component in
# the file → matcher falls back to it.
run_scenario "single_component_no_annotation" "single_component_no_annotation" "github.com/acme/web-app" \
    '.["github.com/acme/web-app"] | (.owner == "group:default/team-web" and .domain == "storefront" and (.tags | sort) == (["bs-frontend","bs-type-website","bs-lifecycle-production"] | sort))'

# ── Scenario: owner_format=bare-name ──────────────────────────────────────
run_scenario "owner_format_bare" "annotation_match" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"].owner == "team-payments"' \
    LUNAR_VAR_OWNER_FORMAT=bare-name

# ── Scenario: default_owner fallback ──────────────────────────────────────
run_scenario "default_owner_fallback" "no_owner" "github.com/acme/orphan" \
    '.["github.com/acme/orphan"].owner == "fallback-team"' \
    LUNAR_VAR_DEFAULT_OWNER=fallback-team

# ── Scenario: include_derived_tags=false drops type-*/lifecycle-* ─────────
run_scenario "no_derived_tags" "annotation_match" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"].tags == ["bs-payments","bs-tier1"]' \
    LUNAR_VAR_INCLUDE_DERIVED_TAGS=false

# ── Scenario: multi-Component file, one entity matches our ID ─────────────
run_scenario "multi_component_one_matches" "multi_component_one_matches" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"] | (.owner == "group:default/team-payments" and .domain == "platform.payments" and (.tags | index("bs-payments") != null) and (.tags | index("bs-tier1") != null))'

# ── Skip scenarios (expect no write) ──────────────────────────────────────
# No file at any configured path (404 from GitHub Contents API)
run_scenario "skip_no_file" "NONE" "github.com/acme/payment-api" ""

# Multi-Component file with annotations, but none matches our ID
run_scenario "skip_multi_none_match" "multi_component_none_match" "github.com/acme/other-repo" ""

# Multi-Component file with no annotations — ambiguous, refuse to guess
run_scenario "skip_multi_no_annotations" "multi_component_no_annotations" "github.com/acme/payment-api" ""

# Annotation-mismatch: annotated single entity but its slug doesn't match
run_scenario "skip_annotation_mismatch" "annotation_match" "github.com/acme/different-repo" ""

# File contains only a System (no Component entity)
run_scenario "skip_non_component" "non_component" "github.com/acme/payments-platform" ""

# Invalid YAML — yq parse failure
run_scenario "skip_invalid_yaml" "invalid" "github.com/acme/payment-api" ""

# Component ID doesn't start with the configured prefix — skip before fetch
run_scenario "skip_prefix_mismatch" "annotation_match" "gitlab.com/acme/payment-api" ""

# ── Summary ───────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Passed: $PASSED  Failed: $FAILED"
echo "=========================================="
if [ "$FAILED" -gt 0 ]; then
    exit 1
fi
