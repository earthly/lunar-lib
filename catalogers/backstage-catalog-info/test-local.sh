#!/bin/bash
#
# Local offline test for the backstage-catalog-info cataloger.
#
# Mocks `curl ... https://api.github.com/repos/.../contents/...` to return
# per-scenario fixtures from test/fixtures/<name>.yaml (absence simulates a
# 404), and mocks `lunar catalog raw --json '.components' -` to capture
# writes to a file. Then asserts the captured output matches the expected
# Catalog JSON entry for that scenario.
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

# --- Mock curl ------------------------------------------------------------
# Implements just enough of `curl -sS -o <body> -w '%{http_code}' ... <URL>` to
# stand in for `main.sh`'s fetch. Looks for $TEST_DIR/fetched.yaml: if present,
# writes its content to the -o file and prints "200"; if absent, writes a
# Not-Found JSON body and prints "404".
cat > "$TEST_DIR/curl" << 'EOF'
#!/bin/bash
set -euo pipefail
TEST_DIR_ENV="${MOCK_CURL_TEST_DIR:?MOCK_CURL_TEST_DIR must be set}"
OUT_PATH=""
while [ $# -gt 0 ]; do
    case "$1" in
        -o)
            OUT_PATH="$2"
            shift 2
            ;;
        -H|-w)
            shift 2
            ;;
        -sS|-sSL|-s|-S|-L)
            shift
            ;;
        *)
            shift
            ;;
    esac
done
if [ -z "$OUT_PATH" ]; then
    echo "Mock curl: -o <path> is required" >&2
    exit 1
fi
if [ -f "$TEST_DIR_ENV/fetched.yaml" ]; then
    cp "$TEST_DIR_ENV/fetched.yaml" "$OUT_PATH"
    printf '200'
    exit 0
fi
printf '{"message":"Not Found"}' > "$OUT_PATH"
printf '404'
exit 0
EOF
chmod +x "$TEST_DIR/curl"

# --- Mock lunar -----------------------------------------------------------
# Handles `lunar catalog raw --json '<path>' -` for `.components` and
# `.domains`. Each write is appended to a per-path .out file so a single
# scenario can be asserted against both maps independently.
cat > "$TEST_DIR/lunar" << 'EOF'
#!/bin/bash
set -euo pipefail
TEST_DIR_ENV="${MOCK_LUNAR_TEST_DIR:?MOCK_LUNAR_TEST_DIR must be set}"
if [ "${1:-}" = "catalog" ] && [ "${2:-}" = "raw" ] && [ "${3:-}" = "--json" ]; then
    case "${4:-}" in
        .components)
            cat >> "$TEST_DIR_ENV/components.out"
            echo "" >> "$TEST_DIR_ENV/components.out"
            exit 0
            ;;
        .domains)
            cat >> "$TEST_DIR_ENV/domains.out"
            echo "" >> "$TEST_DIR_ENV/domains.out"
            exit 0
            ;;
    esac
fi
echo "Mock lunar: unhandled command: $*" >&2
exit 1
EOF
chmod +x "$TEST_DIR/lunar"

export PATH="$TEST_DIR:$PATH"
export MOCK_CURL_TEST_DIR="$TEST_DIR"
export MOCK_LUNAR_TEST_DIR="$TEST_DIR"

# --- Test runner ----------------------------------------------------------
# run_scenario <name> <fixture-or-NONE> <component-id> <expected-jq> [env-overrides...]
# fixture-or-NONE: basename under test/fixtures/, or NONE to simulate 404
# expected-jq: jq filter on merged components.out; "true" means pass.
#              "" means expect no write (skipped scenario)
#
# Optional env overrides may include `EXPECTED_DOMAINS_JQ=<filter>` (the
# only special-cased KEY=VALUE that the runner intercepts before calling
# main.sh) — when set, the runner additionally asserts the filter against
# the merged domains.out and fails if it doesn't evaluate to "true". An
# empty filter (or omitted) means "expect no domain write".
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
    : > "$TEST_DIR/domains.out"
    rm -f "$TEST_DIR/fetched.yaml"

    if [ "$fixture" != "NONE" ]; then
        cp "$FIXTURES_DIR/$fixture.yaml" "$TEST_DIR/fetched.yaml"
    fi

    # Reset env to defaults for each scenario
    unset LUNAR_VAR_COMPONENT_ID_ANNOTATION LUNAR_VAR_COMPONENT_ID_PREFIX
    unset LUNAR_VAR_TAG_PREFIX LUNAR_VAR_INCLUDE_DERIVED_TAGS
    unset LUNAR_VAR_OWNER_FORMAT LUNAR_VAR_DEFAULT_OWNER
    unset LUNAR_VAR_PATHS LUNAR_VAR_BRANCH

    local expected_domains_jq=""
    local kv
    for kv in "$@"; do
        if [[ "$kv" == EXPECTED_DOMAINS_JQ=* ]]; then
            expected_domains_jq="${kv#EXPECTED_DOMAINS_JQ=}"
        else
            export "$kv"
        fi
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
    local merged_domains
    if [ -s "$TEST_DIR/domains.out" ]; then
        merged_domains=$(jq -s 'add // {}' "$TEST_DIR/domains.out" 2>/dev/null || echo '{}')
    else
        merged_domains='{}'
    fi

    local component_check_ok=1
    if [ -z "$expected_jq" ]; then
        if [ "$merged" = "{}" ]; then
            component_check_ok=1
        else
            echo "  FAIL (expected no component write, got):"
            echo "$merged" | jq . | sed 's/^/    /'
            component_check_ok=0
        fi
    else
        local check
        check=$(echo "$merged" | jq -r "$expected_jq" 2>&1 || echo "JQ_ERROR")
        if [ "$check" = "true" ]; then
            component_check_ok=1
        else
            echo "  FAIL — component assertion did not pass (got: $check)"
            echo "  merged components:"
            echo "$merged" | jq . | sed 's/^/    /'
            echo "  jq filter: $expected_jq"
            component_check_ok=0
        fi
    fi

    local domain_check_ok=1
    if [ -z "$expected_domains_jq" ]; then
        if [ "$merged_domains" != "{}" ]; then
            echo "  FAIL (expected no domain write, got):"
            echo "$merged_domains" | jq . | sed 's/^/    /'
            domain_check_ok=0
        fi
    else
        local dcheck
        dcheck=$(echo "$merged_domains" | jq -r "$expected_domains_jq" 2>&1 || echo "JQ_ERROR")
        if [ "$dcheck" != "true" ]; then
            echo "  FAIL — domain assertion did not pass (got: $dcheck)"
            echo "  merged domains:"
            echo "$merged_domains" | jq . | sed 's/^/    /'
            echo "  jq filter: $expected_domains_jq"
            domain_check_ok=0
        fi
    fi

    if [ "$component_check_ok" = "1" ] && [ "$domain_check_ok" = "1" ]; then
        if [ -z "$expected_jq" ]; then
            echo "  OK (correctly skipped — no write)"
        else
            echo "  OK"
            echo "  components:"
            echo "$merged" | jq . | sed 's/^/    /'
            if [ "$merged_domains" != "{}" ]; then
                echo "  domains:"
                echo "$merged_domains" | jq . | sed 's/^/    /'
            fi
        fi
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
}

# ── Scenario: annotation match, defaults ──────────────────────────────────
# Component refs domain "platform.payments"; no Domain entity in the file
# with that metadata.name → empty domain stub keeps validateDomainRefs happy.
run_scenario "annotation_match" "annotation_match" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"] | (.owner == "group:default/team-payments" and .domain == "platform.payments" and (.tags | sort) == (["bs-payments","bs-tier1","bs-type-service","bs-lifecycle-production"] | sort))' \
    'EXPECTED_DOMAINS_JQ=.["platform.payments"] == {}'

# ── Scenario: single-Component-no-annotation fallback ─────────────────────
# Component has no project-slug annotation, but it's the only Component in
# the file → matcher falls back to it. Domain is derived from spec.system
# ("storefront") since spec.domain is absent — bare name, empty stub.
run_scenario "single_component_no_annotation" "single_component_no_annotation" "github.com/acme/web-app" \
    '.["github.com/acme/web-app"] | (.owner == "group:default/team-web" and .domain == "storefront" and (.tags | sort) == (["bs-frontend","bs-type-website","bs-lifecycle-production"] | sort))' \
    'EXPECTED_DOMAINS_JQ=.["storefront"] == {}'

# ── Scenario: owner_format=bare-name ──────────────────────────────────────
run_scenario "owner_format_bare" "annotation_match" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"].owner == "team-payments"' \
    LUNAR_VAR_OWNER_FORMAT=bare-name \
    'EXPECTED_DOMAINS_JQ=.["platform.payments"] == {}'

# ── Scenario: default_owner fallback ──────────────────────────────────────
# no_owner fixture has no spec.domain / spec.system → no domain emission.
run_scenario "default_owner_fallback" "no_owner" "github.com/acme/orphan" \
    '.["github.com/acme/orphan"].owner == "fallback-team"' \
    LUNAR_VAR_DEFAULT_OWNER=fallback-team

# ── Scenario: include_derived_tags=false drops type-*/lifecycle-* ─────────
run_scenario "no_derived_tags" "annotation_match" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"].tags == ["bs-payments","bs-tier1"]' \
    LUNAR_VAR_INCLUDE_DERIVED_TAGS=false \
    'EXPECTED_DOMAINS_JQ=.["platform.payments"] == {}'

# ── Scenario: multi-Component file, one entity matches our ID ─────────────
# System "payments-platform" in the file doesn't match the domain name
# "platform.payments", so the stub stays empty.
run_scenario "multi_component_one_matches" "multi_component_one_matches" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"] | (.owner == "group:default/team-payments" and .domain == "platform.payments" and (.tags | index("bs-payments") != null) and (.tags | index("bs-tier1") != null))' \
    'EXPECTED_DOMAINS_JQ=.["platform.payments"] == {}'

# ── Scenario: Domain entity in the same YAML → pull description + owner ──
# A kind:Domain entity with metadata.name matching the component's
# spec.domain populates the .domains entry instead of leaving it empty.
run_scenario "domain_entity_in_yaml" "domain_entity_in_yaml" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"].domain == "platform.payments"' \
    'EXPECTED_DOMAINS_JQ=.["platform.payments"] | (.description == "Payments platform — billing, ledger, settlement" and .owner == "group:default/team-payments")'

# ── Scenario: domain_annotation sources domain from a custom annotation ───
# Component has no spec.domain / spec.system but carries a custom
# pantalasa.org/domain annotation. Setting domain_annotation makes the
# cataloger pick up that annotation instead.
run_scenario "domain_from_annotation" "domain_from_annotation" "github.com/acme/observability-gateway-dashboard" \
    '.["github.com/acme/observability-gateway-dashboard"].domain == "engineering.tooling.observability"' \
    LUNAR_VAR_DOMAIN_ANNOTATION=pantalasa.org/domain \
    'EXPECTED_DOMAINS_JQ=.["engineering.tooling.observability"] == {}'

# ── Scenario: domain_annotation falls back to spec.domain when absent ────
# annotation_match has spec.domain=platform.payments and no custom domain
# annotation. Setting domain_annotation to a key the entity doesn't carry
# falls back to spec.domain.
run_scenario "domain_annotation_fallback" "annotation_match" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"].domain == "platform.payments"' \
    LUNAR_VAR_DOMAIN_ANNOTATION=pantalasa.org/domain \
    'EXPECTED_DOMAINS_JQ=.["platform.payments"] == {}'

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
