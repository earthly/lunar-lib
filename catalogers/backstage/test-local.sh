#!/bin/bash
#
# Local offline test for the Backstage cataloger.
#
# Mocks both `curl` (against <api_path_prefix>/catalog/entities) and `lunar` (capturing
# catalog writes) so the cataloger can be exercised end-to-end without
# network access. The mock curl serves the bundled sample-catalog.json on
# the first request and an empty array on subsequent requests to terminate
# pagination.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR=$(mktemp -d)
COMPONENTS_OUT="$TEST_DIR/components.json"
DOMAINS_OUT="$TEST_DIR/domains.json"
CURL_CALLS="$TEST_DIR/curl-calls"
CURL_URLS="$TEST_DIR/curl-urls"

trap 'rm -rf "$TEST_DIR"' EXIT

echo "Test directory: $TEST_DIR"

# --- Mock curl ------------------------------------------------------------
# Serves the sample catalog once, then empty arrays. Writes the actual HTTP
# response body to whatever file curl was told to write to via -o, and
# echoes 200 to stdout so curl's -w '%{http_code}' contract is preserved.
cat > "$TEST_DIR/curl" << EOF
#!/bin/bash
# Mock curl — first call returns the fixture, subsequent calls return [].
OUT=""
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
if [ "\$CALL_NUM" = "0" ]; then
    cp "$SCRIPT_DIR/sample-catalog.json" "\$WRITE_FILE"
else
    echo "[]" > "\$WRITE_FILE"
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
"$SCRIPT_DIR/main.sh"

echo ""
echo "=== Captured .components ==="
jq -s 'add // {}' "$COMPONENTS_OUT"

echo ""
echo "=== Captured .domains ==="
jq -s 'add // {}' "$DOMAINS_OUT"

echo ""
echo "=== Requested URLs ==="
cat "$CURL_URLS"

echo ""
echo "=== Summary ==="
echo "Components: $(jq -s 'add // {} | keys | length' "$COMPONENTS_OUT")"
echo "Domains:    $(jq -s 'add // {} | keys | length' "$DOMAINS_OUT")"
echo "curl calls: $(wc -l < "$CURL_CALLS")"

# --- Assert api_path_prefix plumbing -------------------------------------
# The resolved prefix must sit directly before /catalog/entities. Normalize
# the same way main.sh does (drop trailing slash, ensure leading slash) so the
# expectation holds for the default, the empty (root-mounted) case, and any
# custom prefix passed via TEST_API_PATH_PREFIX.
NP="${LUNAR_VAR_API_PATH_PREFIX%/}"
if [ -n "$NP" ] && [ "${NP#/}" = "$NP" ]; then NP="/$NP"; fi
EXPECT="${LUNAR_VAR_BACKSTAGE_URL}${NP}/catalog/entities"
FIRST_URL=$(head -1 "$CURL_URLS")
case "$FIRST_URL" in
    "$EXPECT"?*)
        echo "PASS: request URL uses api_path_prefix='${NP:-<none>}' → $EXPECT" ;;
    *)
        echo "FAIL: expected request URL to start with '$EXPECT' but got '$FIRST_URL'" >&2
        exit 1 ;;
esac
