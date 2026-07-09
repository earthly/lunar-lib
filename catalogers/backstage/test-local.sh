#!/bin/bash
#
# Local offline test for the Backstage cataloger.
#
# Mocks `curl` (against the by-query catalog endpoint) and `lunar` (capturing
# catalog writes) so the cataloger runs end-to-end without network access.
#
# The mock serves the bundled sample-catalog.json as a paginated
# /catalog/entities/by-query response: it splits the fixture's `.items` across
# TWO pages and only advances to page 2 when the request carries the cursor as
# `cursor=<value>` — exactly how real Backstage behaves (it ignores an unknown
# key such as `after=` and just re-serves page 1). That makes the multi-page
# path a real assertion: a regression to the wrong query-param name re-serves
# page 1 forever and trips the "exactly 2 requests" / "domains came back" checks
# below. (This is the bug class that shipped in the by-query migration.)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURE="$SCRIPT_DIR/sample-catalog.json"
TEST_DIR=$(mktemp -d)
COMPONENTS_OUT="$TEST_DIR/components.json"
DOMAINS_OUT="$TEST_DIR/domains.json"
CURL_CALLS="$TEST_DIR/curl-calls"
CURL_URLS="$TEST_DIR/curl-urls"
RUN_OUT="$TEST_DIR/run.out"

trap 'rm -rf "$TEST_DIR"' EXIT

echo "Test directory: $TEST_DIR"

# --- Mock curl ------------------------------------------------------------
# Returns by-query envelopes: page 1 = items[0:5] + pageInfo.nextCursor, page 2
# (only when the URL contains cursor=CURSOR_P2) = items[5:] with no nextCursor.
# A safety valve returns an empty page after several calls so a pagination
# regression fails an assertion instead of hanging CI.
cat > "$TEST_DIR/curl" << EOF
#!/bin/bash
WRITE_FILE=""
REQ_URL=""
while [ \$# -gt 0 ]; do
    case "\$1" in
        -o) WRITE_FILE="\$2"; shift 2 ;;
        -w) shift 2 ;;
        -sS|-H|-X) shift 1; [ \$# -gt 0 ] && case "\$1" in -*) ;; *) shift 1 ;; esac ;;
        *) REQ_URL="\$1"; shift 1 ;;
    esac
done
echo "\$REQ_URL" >> "$CURL_URLS"
CALL_NUM=\$(wc -l < "$CURL_CALLS" 2>/dev/null || echo 0)
echo "call \$((CALL_NUM + 1))" >> "$CURL_CALLS"
if [ "\$CALL_NUM" -ge 4 ]; then
    echo '{"items":[],"pageInfo":{}}' > "\$WRITE_FILE"
elif echo "\$REQ_URL" | grep -q 'cursor=CURSOR_P2'; then
    jq -c '{items: .items[5:], pageInfo: {}}' "$FIXTURE" > "\$WRITE_FILE"
else
    jq -c '{items: .items[0:5], pageInfo: {nextCursor: "CURSOR_P2"}}' "$FIXTURE" > "\$WRITE_FILE"
fi
echo "200"
EOF
chmod +x "$TEST_DIR/curl"

# --- Mock lunar -----------------------------------------------------------
cat > "$TEST_DIR/lunar" << EOF
#!/bin/bash
# Mock lunar — captures catalog writes to per-path files.
if [ "\$1" = "catalog" ] && [ "\$2" = "raw" ] && [ "\$3" = "--json" ]; then
    case "\$4" in
        .components) cat >> "$COMPONENTS_OUT" ;;
        .domains)    cat >> "$DOMAINS_OUT" ;;
        *) echo "Mock lunar: unknown path: \$4" >&2; exit 1 ;;
    esac
    echo ""  # newline between batches
else
    echo "Mock lunar: unhandled command: \$@" >&2
    exit 1
fi
EOF
chmod +x "$TEST_DIR/lunar"

export PATH="$TEST_DIR:$PATH"

# --- Cataloger inputs -----------------------------------------------------
export LUNAR_VAR_BACKSTAGE_URL="${TEST_BACKSTAGE_URL:-https://backstage.example.com}"
# `-` not `:-` so `TEST_API_PATH_PREFIX=""` exercises the root-mounted case
# (no /api hop), mirroring how the hub forwards an explicit empty config value.
export LUNAR_VAR_API_PATH_PREFIX="${TEST_API_PATH_PREFIX-/api}"
export LUNAR_VAR_ENTITY_KINDS="${TEST_ENTITY_KINDS:-Component,Domain,System,API,Resource}"
export LUNAR_VAR_NAMESPACE="${TEST_NAMESPACE:-default}"
export LUNAR_VAR_COMPONENT_ID_ANNOTATION="${TEST_COMPONENT_ID_ANNOTATION:-github.com/project-slug}"
export LUNAR_VAR_COMPONENT_ID_PREFIX="${TEST_COMPONENT_ID_PREFIX:-github.com/}"
export LUNAR_VAR_TAG_PREFIX="${TEST_TAG_PREFIX:-bs-}"
export LUNAR_VAR_INCLUDE_DERIVED_TAGS="${TEST_INCLUDE_DERIVED_TAGS:-true}"
export LUNAR_VAR_OWNER_FORMAT="${TEST_OWNER_FORMAT:-as-is}"
export LUNAR_VAR_DEFAULT_OWNER="${TEST_DEFAULT_OWNER:-}"
export LUNAR_VAR_DOMAIN_DEFAULT_DESCRIPTION="${TEST_DOMAIN_DEFAULT_DESCRIPTION:-}"
export LUNAR_VAR_FILTER="${TEST_FILTER:-}"
export LUNAR_SECRET_BACKSTAGE_TOKEN="${TEST_BACKSTAGE_TOKEN:-mock-token}"

# Speed up the mocked retry path
export PAGE_SIZE="${PAGE_SIZE:-200}"
export INITIAL_BACKOFF="${INITIAL_BACKOFF:-1}"

echo ""
echo "=== Running cataloger with settings ==="
echo "Backstage URL:  $LUNAR_VAR_BACKSTAGE_URL"
echo "API path prefix: ${LUNAR_VAR_API_PATH_PREFIX:-<none>}"
echo "Kinds:          $LUNAR_VAR_ENTITY_KINDS"
echo "Namespace:      $LUNAR_VAR_NAMESPACE"
echo "Owner format:   $LUNAR_VAR_OWNER_FORMAT"
echo "Tag prefix:     $LUNAR_VAR_TAG_PREFIX"
echo ""

# Initialize capture files
: > "$COMPONENTS_OUT"
: > "$DOMAINS_OUT"
: > "$CURL_CALLS"
: > "$CURL_URLS"

echo "=== Cataloger output ==="
"$SCRIPT_DIR/main.sh" 2>&1 | tee "$RUN_OUT"

echo ""
echo "=== Captured .components ==="
jq -s 'add // {}' "$COMPONENTS_OUT"

echo ""
echo "=== Captured .domains ==="
jq -s 'add // {}' "$DOMAINS_OUT"

echo ""
echo "=== Requested URLs ==="
cat "$CURL_URLS"

COMPONENTS_GOT=$(jq -s 'add // {} | keys | length' "$COMPONENTS_OUT")
DOMAINS_GOT=$(jq -s 'add // {} | keys | length' "$DOMAINS_OUT")
CALLS=$(wc -l < "$CURL_CALLS")

echo ""
echo "=== Summary ==="
echo "Components: $COMPONENTS_GOT"
echo "Domains:    $DOMAINS_GOT"
echo "curl calls: $CALLS"

# --- Expected values, derived from the fixture ---------------------------
# Components come from Component/API/Resource entities that carry the id
# annotation (keyed by it, so dedup on that value). Domains come from
# Domain/System entities (keyed by name). Total = every item across all pages.
EXPECTED_TOTAL=$(jq '.items | length' "$FIXTURE")
EXPECTED_COMPONENTS=$(jq --arg ann "$LUNAR_VAR_COMPONENT_ID_ANNOTATION" \
    '[.items[] | select(.kind=="Component" or .kind=="API" or .kind=="Resource")
       | (.metadata.annotations[$ann] // "")] | map(select(. != "")) | unique | length' "$FIXTURE")
EXPECTED_DOMAINS=$(jq \
    '[.items[] | select(.kind=="Domain" or .kind=="System") | .metadata.name] | unique | length' "$FIXTURE")

# --- Assertions ----------------------------------------------------------
FAILED=0
fail() { echo "FAIL: $1" >&2; FAILED=1; }

# 1. Pagination advanced via cursor= and terminated after exactly two pages.
#    A wrong param name (e.g. after=) re-serves page 1 -> more than 2 calls.
[ "$CALLS" -eq 2 ] || fail "expected exactly 2 paginated requests, got $CALLS — pagination did not advance/terminate cleanly (wrong cursor param re-serves page 1?)"

# 2. The page-2 request carried the cursor as cursor=, and nothing used after=.
SECOND_URL=$(sed -n '2p' "$CURL_URLS")
case "$SECOND_URL" in
    *"cursor=CURSOR_P2"*) : ;;
    *) fail "page-2 request must send cursor=CURSOR_P2; got: ${SECOND_URL:-<none>}" ;;
esac
if grep -q 'after=' "$CURL_URLS"; then
    fail "a request used after= — Backstage by-query expects cursor="
fi

# 3. Every entity across BOTH pages was collected. Domains live entirely on
#    page 2, so a correct domain count also proves page 2 was fetched+parsed.
if grep -q "Total entities fetched: $EXPECTED_TOTAL" "$RUN_OUT"; then :; else
    fail "expected 'Total entities fetched: $EXPECTED_TOTAL' in output"
fi
[ "$COMPONENTS_GOT" -eq "$EXPECTED_COMPONENTS" ] || fail "expected $EXPECTED_COMPONENTS components, got $COMPONENTS_GOT"
[ "$DOMAINS_GOT" -eq "$EXPECTED_DOMAINS" ] || fail "expected $EXPECTED_DOMAINS domains, got $DOMAINS_GOT (page 2 not consumed?)"

# 4. The api_path_prefix sits directly before /catalog/entities/by-query.
#    Normalize the prefix the same way main.sh does so this holds for the
#    default, the empty (root-mounted) case, and any custom TEST_API_PATH_PREFIX.
NP="${LUNAR_VAR_API_PATH_PREFIX%/}"
if [ -n "$NP" ] && [ "${NP#/}" = "$NP" ]; then NP="/$NP"; fi
EXPECT="${LUNAR_VAR_BACKSTAGE_URL}${NP}/catalog/entities/by-query"
FIRST_URL=$(head -1 "$CURL_URLS")
case "$FIRST_URL" in
    "$EXPECT"?*) : ;;
    *) fail "expected first request URL to start with '$EXPECT' but got '$FIRST_URL'" ;;
esac

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo "PASS: 2-page cursor pagination, api_path_prefix='${NP:-<none>}', $COMPONENTS_GOT components + $DOMAINS_GOT domains"
else
    echo "TEST FAILED" >&2
    exit 1
fi
