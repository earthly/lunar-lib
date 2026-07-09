#!/bin/bash
#
# Local offline test for the backstage-catalog-info cataloger.
#
# Exercises BOTH entrypoints against the same fixtures and asserts identical
# Catalog JSON output — they share helpers.sh, so only the acquisition step
# differs:
#   - main.sh           (component-cron):  a fake `curl` returns the fixture,
#                        standing in for the GitHub Contents API fetch.
#   - main-on-commit.sh (component-repo):  the fixture is written into a temp
#                        checkout dir and the script runs with it as CWD.
# `lunar catalog raw` is mocked in both cases to capture writes to a file.
#
# Every scenario runs against both variants; any failure is logged with a diff
# and the script exits non-zero at the end.

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

FAILED=0
PASSED=0

# indent: prefix every line of stdin with 4 spaces (for readable log nesting).
indent() {
    sed 's/^/    /'
}

# Reset cataloger inputs to defaults between variant runs.
reset_env() {
    unset LUNAR_VAR_COMPONENT_ID_ANNOTATION LUNAR_VAR_COMPONENT_ID_PREFIX
    unset LUNAR_VAR_TAG_PREFIX LUNAR_VAR_INCLUDE_DERIVED_TAGS
    unset LUNAR_VAR_OWNER_FORMAT LUNAR_VAR_DEFAULT_OWNER
    unset LUNAR_VAR_PATHS LUNAR_VAR_BRANCH
    unset LUNAR_VAR_DOMAIN_ANNOTATION LUNAR_VAR_DEFAULT_DOMAIN
    unset LUNAR_VAR_META_ANNOTATIONS
}

# check_output <label> <expected_jq> <expected_domains_jq>
# Asserts the captured components.out / domains.out against the expected jq
# filters (a filter of "" means "expect no write"). Bumps PASSED/FAILED.
check_output() {
    local label="$1"
    local expected_jq="$2"
    local expected_domains_jq="$3"

    local merged merged_domains
    if [ -s "$TEST_DIR/components.out" ]; then
        merged=$(jq -s 'add // {}' "$TEST_DIR/components.out" 2>/dev/null || echo '{}')
    else
        merged='{}'
    fi
    if [ -s "$TEST_DIR/domains.out" ]; then
        merged_domains=$(jq -s 'add // {}' "$TEST_DIR/domains.out" 2>/dev/null || echo '{}')
    else
        merged_domains='{}'
    fi

    local component_check_ok=1
    if [ -z "$expected_jq" ]; then
        if [ "$merged" != "{}" ]; then
            echo "  [$label] FAIL (expected no component write, got):"
            echo "$merged" | jq . | sed 's/^/    /'
            component_check_ok=0
        fi
    else
        local check
        check=$(echo "$merged" | jq -r "$expected_jq" 2>&1 || echo "JQ_ERROR")
        if [ "$check" != "true" ]; then
            echo "  [$label] FAIL — component assertion did not pass (got: $check)"
            echo "  merged components:"
            echo "$merged" | jq . | sed 's/^/    /'
            echo "  jq filter: $expected_jq"
            component_check_ok=0
        fi
    fi

    local domain_check_ok=1
    if [ -z "$expected_domains_jq" ]; then
        if [ "$merged_domains" != "{}" ]; then
            echo "  [$label] FAIL (expected no domain write, got):"
            echo "$merged_domains" | jq . | sed 's/^/    /'
            domain_check_ok=0
        fi
    else
        local dcheck
        dcheck=$(echo "$merged_domains" | jq -r "$expected_domains_jq" 2>&1 || echo "JQ_ERROR")
        if [ "$dcheck" != "true" ]; then
            echo "  [$label] FAIL — domain assertion did not pass (got: $dcheck)"
            echo "  merged domains:"
            echo "$merged_domains" | jq . | sed 's/^/    /'
            echo "  jq filter: $expected_domains_jq"
            domain_check_ok=0
        fi
    fi

    if [ "$component_check_ok" = "1" ] && [ "$domain_check_ok" = "1" ]; then
        if [ -z "$expected_jq" ]; then
            echo "  [$label] OK (correctly skipped — no write)"
        else
            echo "  [$label] OK"
        fi
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
}

# run_scenario <name> <fixture-or-NONE> <component-id> <expected-jq> [env-overrides...]
# fixture-or-NONE: basename under test/fixtures/, or NONE to simulate absence.
# expected-jq: jq filter on merged components.out; "true" means pass.
#              "" means expect no write (skipped scenario).
# Optional env override `EXPECTED_DOMAINS_JQ=<filter>` is intercepted to assert
# the merged domains.out; empty/omitted means "expect no domain write".
# Each scenario runs through BOTH entrypoints; output must match.
run_scenario() {
    local name="$1"
    local fixture="$2"
    local component_id="$3"
    local expected_jq="$4"
    shift 4

    echo "── scenario: $name ──"

    local expected_domains_jq=""
    local kv
    local -a env_overrides=()
    for kv in "$@"; do
        if [[ "$kv" == EXPECTED_DOMAINS_JQ=* ]]; then
            expected_domains_jq="${kv#EXPECTED_DOMAINS_JQ=}"
        else
            env_overrides+=("$kv")
        fi
    done

    local log

    # ── variant: api (main.sh / component-cron) ──────────────────────────
    : > "$TEST_DIR/components.out"
    : > "$TEST_DIR/domains.out"
    rm -f "$TEST_DIR/fetched.yaml"
    reset_env
    if [ "$fixture" != "NONE" ]; then
        cp "$FIXTURES_DIR/$fixture.yaml" "$TEST_DIR/fetched.yaml"
    fi
    if [ ${#env_overrides[@]} -gt 0 ]; then
        export "${env_overrides[@]}"
    fi
    export LUNAR_COMPONENT_ID="$component_id"
    export LUNAR_SECRET_GH_TOKEN="test-token-stub"
    if log=$("$SCRIPT_DIR/main.sh" 2>&1); then
        check_output "api" "$expected_jq" "$expected_domains_jq"
    else
        echo "  [api] main.sh exited non-zero — FAIL"
        echo "$log" | indent
        FAILED=$((FAILED + 1))
    fi

    # ── variant: commit (main-on-commit.sh / component-repo) ─────────────
    : > "$TEST_DIR/components.out"
    : > "$TEST_DIR/domains.out"
    local checkout="$TEST_DIR/checkout"
    rm -rf "$checkout"
    mkdir -p "$checkout"
    reset_env
    if [ "$fixture" != "NONE" ]; then
        cp "$FIXTURES_DIR/$fixture.yaml" "$checkout/catalog-info.yaml"
    fi
    if [ ${#env_overrides[@]} -gt 0 ]; then
        export "${env_overrides[@]}"
    fi
    export LUNAR_COMPONENT_ID="$component_id"
    unset LUNAR_SECRET_GH_TOKEN   # commit variant needs no token
    if log=$(cd "$checkout" && "$SCRIPT_DIR/main-on-commit.sh" 2>&1); then
        check_output "commit" "$expected_jq" "$expected_domains_jq"
    else
        echo "  [commit] main-on-commit.sh exited non-zero — FAIL"
        echo "$log" | indent
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

# ── Scenario: tag_prefix="" disables prefixing entirely ───────────────────
# An explicit empty tag_prefix must pass through un-prefixed, per the
# documented "empty string disables the prefix" contract. Regression guard:
# the old `${LUNAR_VAR_TAG_PREFIX:-bs-}` clobbered a config-supplied empty
# value back to "bs-", so this scenario failed (tags came out "bs-*").
run_scenario "tag_prefix_disabled" "annotation_match" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"] | (.tags | sort) == (["payments","tier1","type-service","lifecycle-production"] | sort)' \
    LUNAR_VAR_TAG_PREFIX= \
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

# ── Scenario: default_domain fills in when the file resolves no domain ────
# no_owner has no spec.domain / spec.system / domain annotation, so the
# domain would normally be omitted. default_domain supplies the fallback
# and a matching empty domain stub is written for validateDomainRefs.
run_scenario "default_domain_fallback" "no_owner" "github.com/acme/orphan" \
    '.["github.com/acme/orphan"].domain == "unassigned"' \
    LUNAR_VAR_DEFAULT_DOMAIN=unassigned \
    'EXPECTED_DOMAINS_JQ=.["unassigned"] == {}'

# ── Scenario: default_domain does NOT override a resolved domain ──────────
# annotation_match has spec.domain=platform.payments; default_domain is a
# last-resort fallback only, so the real domain wins and "unassigned" is
# never written.
run_scenario "default_domain_no_override" "annotation_match" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"].domain == "platform.payments"' \
    LUNAR_VAR_DEFAULT_DOMAIN=unassigned \
    'EXPECTED_DOMAINS_JQ=(.["platform.payments"] == {}) and (has("unassigned") | not)'

# ── Scenario: default meta_annotations maps pagerduty.com/service-id ──────
# The pagerduty_annotation fixture carries pagerduty.com/service-id=PABC123.
# With the default meta_annotations mapping, that lands in
# .meta["pagerduty/service-id"] — what the pagerduty collector reads from
# LUNAR_COMPONENT_META.
run_scenario "meta_pagerduty_default" "pagerduty_annotation" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"].meta == {"pagerduty/service-id": "PABC123"}' \
    'EXPECTED_DOMAINS_JQ=.["platform.payments"] == {}'

# ── Scenario: no meta when the mapped annotation is absent ────────────────
# annotation_match has no pagerduty.com/service-id annotation, so with the
# default mapping no meta key is emitted (.meta is omitted entirely).
run_scenario "meta_absent_annotation" "annotation_match" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"] | (has("meta") | not)' \
    'EXPECTED_DOMAINS_JQ=.["platform.payments"] == {}'

# ── Scenario: custom meta_annotations mapping (tolerates whitespace) ──────
# A custom mapping picks a different annotation/target key and tolerates
# surrounding whitespace around the pair and the '='.
run_scenario "meta_custom_mapping" "pagerduty_annotation" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"].meta == {"pagerduty/integration-key": "0123456789abcdef0123456789abcdef"}' \
    'LUNAR_VAR_META_ANNOTATIONS= pagerduty.com/integration-key = pagerduty/integration-key ' \
    'EXPECTED_DOMAINS_JQ=.["platform.payments"] == {}'

# ── Scenario: explicitly-empty meta_annotations disables meta mapping ─────
run_scenario "meta_disabled" "pagerduty_annotation" "github.com/acme/payment-api" \
    '.["github.com/acme/payment-api"] | (has("meta") | not)' \
    LUNAR_VAR_META_ANNOTATIONS= \
    'EXPECTED_DOMAINS_JQ=.["platform.payments"] == {}'

# ── Skip scenarios (expect no write) ──────────────────────────────────────
# No file at any configured path (404 from GitHub Contents API / absent in checkout)
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

# Component ID doesn't start with the configured prefix. main.sh skips before
# the fetch; main-on-commit.sh reads the checkout but the matcher finds no
# annotated entity equal to the (non-github) ID, so it skips too — both no-write.
run_scenario "skip_prefix_mismatch" "annotation_match" "gitlab.com/acme/payment-api" ""

# ── Summary ───────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Passed: $PASSED  Failed: $FAILED"
echo "=========================================="
if [ "$FAILED" -gt 0 ]; then
    exit 1
fi
