#!/bin/bash
#
# Local offline test for the backstage-catalog-info-monorepo cataloger.
#
# Exercises the `discover` (cron) entrypoint against a fake repository. `curl`
# is mocked to stand in for the three GitHub API calls the cataloger makes:
#   - GET /repos/<slug>                    -> {"default_branch": "main"}
#   - GET /repos/<slug>/git/trees/<ref>    -> a tree built from the fake repo dir
#   - GET /repos/<slug>/contents/<path>    -> the file at that path in the dir
# `lunar catalog raw` is mocked to capture writes to per-path .out files.
#
# Each scenario lays out catalog-info files at chosen paths in a fresh fake
# repo, runs main.sh, and asserts the created components / domains. Any failure
# is logged and the script exits non-zero at the end.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR=$(mktemp -d)
FIXTURES_DIR="$SCRIPT_DIR/test/fixtures"
REPO_DIR="$TEST_DIR/repo"

trap 'rm -rf "$TEST_DIR"' EXIT

echo "Test directory: $TEST_DIR"
echo ""

# --- Mock curl ------------------------------------------------------------
cat > "$TEST_DIR/curl" << 'EOF'
#!/bin/bash
set -euo pipefail
REPO_DIR_ENV="${MOCK_REPO_DIR:?MOCK_REPO_DIR must be set}"
OUT=""
URL=""
while [ $# -gt 0 ]; do
    case "$1" in
        -o) OUT="$2"; shift 2 ;;
        -H|-w) shift 2 ;;
        -sS|-s|-S|-L|-sSL) shift ;;
        http*|https*) URL="$1"; shift ;;
        *) shift ;;
    esac
done
[ -z "$OUT" ] && { echo "mock curl: -o required" >&2; exit 1; }
case "$URL" in
    *"/git/trees/"*)
        ( cd "$REPO_DIR_ENV" && find . -type f | sed 's|^\./||' ) \
            | jq -R -s 'split("\n") | map(select(length > 0))
                        | {tree: map({path: ., type: "blob"}), truncated: false}' > "$OUT"
        printf '200'
        ;;
    *"/contents/"*)
        p="${URL#*/contents/}"; p="${p%%\?*}"
        if [ -f "$REPO_DIR_ENV/$p" ]; then
            cat "$REPO_DIR_ENV/$p" > "$OUT"; printf '200'
        else
            printf '{"message":"Not Found"}' > "$OUT"; printf '404'
        fi
        ;;
    *"/repos/"*)
        printf '{"default_branch":"main"}' > "$OUT"; printf '200'
        ;;
    *)
        printf '{"message":"unhandled"}' > "$OUT"; printf '404'
        ;;
esac
exit 0
EOF
chmod +x "$TEST_DIR/curl"

# --- Mock lunar -----------------------------------------------------------
cat > "$TEST_DIR/lunar" << 'EOF'
#!/bin/bash
set -euo pipefail
TEST_DIR_ENV="${MOCK_LUNAR_TEST_DIR:?MOCK_LUNAR_TEST_DIR must be set}"
if [ "${1:-}" = "catalog" ] && [ "${2:-}" = "raw" ] && [ "${3:-}" = "--json" ]; then
    case "${4:-}" in
        .components) cat >> "$TEST_DIR_ENV/components.out"; echo "" >> "$TEST_DIR_ENV/components.out"; exit 0 ;;
        .domains)    cat >> "$TEST_DIR_ENV/domains.out";    echo "" >> "$TEST_DIR_ENV/domains.out";    exit 0 ;;
    esac
fi
echo "mock lunar: unhandled: $*" >&2
exit 1
EOF
chmod +x "$TEST_DIR/lunar"

export PATH="$TEST_DIR:$PATH"
export MOCK_REPO_DIR="$REPO_DIR"
export MOCK_LUNAR_TEST_DIR="$TEST_DIR"

FAILED=0
PASSED=0

indent() { sed 's/^/    /'; }

reset_env() {
    unset LUNAR_VAR_REPOS LUNAR_VAR_FILENAMES LUNAR_VAR_BRANCH \
          LUNAR_VAR_SKIP_ROOT_FILE LUNAR_VAR_COMPONENT_ID_PREFIX \
          LUNAR_VAR_DOMAIN_ANNOTATION LUNAR_VAR_TAG_PREFIX \
          LUNAR_VAR_INCLUDE_DERIVED_TAGS LUNAR_VAR_OWNER_FORMAT \
          LUNAR_VAR_DEFAULT_OWNER LUNAR_VAR_DEFAULT_DOMAIN 2>/dev/null || true
    export LUNAR_VAR_REPOS="acme/monorepo"
    export LUNAR_SECRET_GH_TOKEN="stub-token"
}

# place <fixture-basename> <path-in-repo>
place() {
    local dest="$REPO_DIR/$2"
    mkdir -p "$(dirname "$dest")"
    cp "$FIXTURES_DIR/$1" "$dest"
}

fresh_repo() { rm -rf "$REPO_DIR"; mkdir -p "$REPO_DIR"; }
reset_out()  { : > "$TEST_DIR/components.out"; : > "$TEST_DIR/domains.out"; }

merged_components() {
    if [ -s "$TEST_DIR/components.out" ]; then jq -s 'add // {}' "$TEST_DIR/components.out" 2>/dev/null || echo '{}'; else echo '{}'; fi
}
merged_domains() {
    if [ -s "$TEST_DIR/domains.out" ]; then jq -s 'add // {}' "$TEST_DIR/domains.out" 2>/dev/null || echo '{}'; else echo '{}'; fi
}

# assert <label> <components-jq> <domains-jq-or-empty>
assert() {
    local label="$1" cjq="$2" djq="$3"
    local c d ok=1
    c=$(merged_components); d=$(merged_domains)
    if [ -z "$cjq" ]; then
        [ "$c" = "{}" ] || { echo "  [$label] FAIL — expected no component writes, got:"; echo "$c" | jq . | indent; ok=0; }
    else
        [ "$(echo "$c" | jq -r "$cjq" 2>&1)" = "true" ] || { echo "  [$label] FAIL — component assertion false ($cjq)"; echo "$c" | jq . | indent; ok=0; }
    fi
    if [ -n "$djq" ]; then
        [ "$(echo "$d" | jq -r "$djq" 2>&1)" = "true" ] || { echo "  [$label] FAIL — domain assertion false ($djq)"; echo "$d" | jq . | indent; ok=0; }
    fi
    if [ "$ok" = "1" ]; then echo "  [$label] OK"; PASSED=$((PASSED+1)); else FAILED=$((FAILED+1)); fi
}

run_main() {
    local log
    if log=$("$SCRIPT_DIR/main.sh" 2>&1); then :; else
        echo "  main.sh exited non-zero:"; echo "$log" | indent; FAILED=$((FAILED+1)); return 1
    fi
}

# ── Scenario: monorepo, two service dirs, skip_root_file default (true) ────
echo "── monorepo_two_services (default skip_root) ──"
fresh_repo; reset_out; reset_env
place payments.yaml "services/payments/catalog-info.yaml"
place web.yaml      "services/web/catalog-info.yaml"
place payments.yaml "catalog-info.yaml"   # root — should be skipped by default
run_main
assert "two subcomponents, root skipped" \
    '(.["github.com/acme/monorepo/services/payments"].owner == "group:default/team-payments")
     and (.["github.com/acme/monorepo/services/payments"].domain == "platform.payments")
     and (.["github.com/acme/monorepo/services/web"].owner == "group:default/team-web")
     and (.["github.com/acme/monorepo/services/web"].domain == "storefront")
     and (has("github.com/acme/monorepo") | not)' \
    '(.["platform.payments"] == {}) and (.["storefront"] == {})'

# ── Scenario: skip_root_file=false → root file also becomes repo-level ────
echo "── skip_root_file_false ──"
fresh_repo; reset_out; reset_env
export LUNAR_VAR_SKIP_ROOT_FILE="false"
place payments.yaml "catalog-info.yaml"
place web.yaml      "services/web/catalog-info.yaml"
run_main
assert "root maps to repo-level id + subdir subcomponent" \
    '(.["github.com/acme/monorepo"].owner == "group:default/team-payments")
     and (.["github.com/acme/monorepo/services/web"].owner == "group:default/team-web")' \
    ''

# ── Scenario: deeply nested dir + .yml extension ─────────────────────────
echo "── nested_and_yml ──"
fresh_repo; reset_out; reset_env
place payments.yaml "a/b/c/catalog-info.yml"
run_main
assert "deep path keyed correctly, .yml recognized" \
    '.["github.com/acme/monorepo/a/b/c"].owner == "group:default/team-payments"' ''

# ── Scenario: Component + Domain entity in one file → enriched stub ───────
echo "── domain_entity_enriched ──"
fresh_repo; reset_out; reset_env
place with_domain.yaml "services/payments/catalog-info.yaml"
run_main
assert "domain stub enriched from Domain entity" \
    '.["github.com/acme/monorepo/services/payments"].domain == "platform.payments"' \
    '.["platform.payments"] | (.description == "Payments platform — billing, ledger, settlement" and .owner == "group:default/team-payments")'

# ── Scenario: file with multiple Components → skipped (ambiguous) ─────────
echo "── multi_component_skipped ──"
fresh_repo; reset_out; reset_env
place multi_component.yaml "services/multi/catalog-info.yaml"
run_main
assert "ambiguous multi-Component file skipped" "" ""

# ── Scenario: file with no Component (only System) → skipped ─────────────
echo "── only_system_skipped ──"
fresh_repo; reset_out; reset_env
place only_system.yaml "services/sys/catalog-info.yaml"
run_main
assert "file with no Component skipped" "" ""

# ── Scenario: repo has no catalog-info files → no writes ─────────────────
echo "── no_descriptors ──"
fresh_repo; reset_out; reset_env
mkdir -p "$REPO_DIR/src"; echo "package main" > "$REPO_DIR/src/main.go"
run_main
assert "no catalog-info files → no writes" "" ""

# ── Scenario: owner_format=bare-name ─────────────────────────────────────
echo "── owner_format_bare ──"
fresh_repo; reset_out; reset_env
export LUNAR_VAR_OWNER_FORMAT="bare-name"
place payments.yaml "services/payments/catalog-info.yaml"
run_main
assert "bare-name strips kind:namespace/" \
    '.["github.com/acme/monorepo/services/payments"].owner == "team-payments"' ''

# ── Scenario: tag_prefix="" disables prefixing ───────────────────────────
echo "── tag_prefix_disabled ──"
fresh_repo; reset_out; reset_env
export LUNAR_VAR_TAG_PREFIX=""
place payments.yaml "services/payments/catalog-info.yaml"
run_main
assert "empty tag_prefix leaves tags unprefixed" \
    '.["github.com/acme/monorepo/services/payments"].tags | sort == (["payments","type-service","lifecycle-production"] | sort)' ''

# ── Scenario: include_derived_tags=false drops type-*/lifecycle-* ─────────
echo "── no_derived_tags ──"
fresh_repo; reset_out; reset_env
export LUNAR_VAR_INCLUDE_DERIVED_TAGS="false"
place payments.yaml "services/payments/catalog-info.yaml"
run_main
assert "derived tags dropped" \
    '.["github.com/acme/monorepo/services/payments"].tags == ["bs-payments"]' ''

# ── Scenario: default_owner fallback + default_domain fallback ───────────
echo "── default_owner_and_domain ──"
fresh_repo; reset_out; reset_env
export LUNAR_VAR_DEFAULT_OWNER="fallback-team"
export LUNAR_VAR_DEFAULT_DOMAIN="unassigned"
place no_owner.yaml "services/orphan/catalog-info.yaml"
run_main
assert "default owner + domain applied" \
    '(.["github.com/acme/monorepo/services/orphan"].owner == "fallback-team")
     and (.["github.com/acme/monorepo/services/orphan"].domain == "unassigned")' \
    '.["unassigned"] == {}'

# ── Scenario: component_id_prefix override ───────────────────────────────
echo "── component_id_prefix ──"
fresh_repo; reset_out; reset_env
export LUNAR_VAR_COMPONENT_ID_PREFIX="ghe.acme.com/"
place payments.yaml "services/payments/catalog-info.yaml"
run_main
assert "custom prefix used in id" \
    '.["ghe.acme.com/acme/monorepo/services/payments"].owner == "group:default/team-payments"' ''

# ── Scenario: no GH_TOKEN → graceful no-op ───────────────────────────────
echo "── no_token ──"
fresh_repo; reset_out; reset_env
unset LUNAR_SECRET_GH_TOKEN
unset GH_TOKEN 2>/dev/null || true
place payments.yaml "services/payments/catalog-info.yaml"
run_main
assert "missing token → no writes, exit 0" "" ""

# ── Scenario: empty repos input → graceful no-op ─────────────────────────
echo "── empty_repos ──"
fresh_repo; reset_out; reset_env
export LUNAR_VAR_REPOS=""
run_main
assert "empty repos → no writes, exit 0" "" ""

echo ""
echo "=========================================="
echo "Passed: $PASSED  Failed: $FAILED"
echo "=========================================="
[ "$FAILED" -gt 0 ] && exit 1 || exit 0
