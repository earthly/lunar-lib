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
GQL_URLS="$TEST_DIR/gql-urls"
GQL_BATCHES="$TEST_DIR/gql-batches"
RUN_OUT="$TEST_DIR/run.out"

trap 'rm -rf "$TEST_DIR"' EXIT

echo "Test directory: $TEST_DIR"

# --- Mock curl ------------------------------------------------------------
# Serves two endpoints:
#
# 1. The Backstage by-query catalog. Returns by-query envelopes: page 1 =
#    items[0:5] + pageInfo.nextCursor, page 2 (only when the URL contains
#    cursor=CURSOR_P2) = items[5:] with no nextCursor. A safety valve returns an
#    empty page after several calls so a pagination regression fails an
#    assertion instead of hanging CI.
#
# 2. The GitHub GraphQL repo-existence check (URL ending /graphql). Reads the
#    posted query from stdin, extracts each `rN: repository(owner: "o", name:
#    "r")` alias, and answers non-null for every slug EXCEPT those listed in
#    $MOCK_MISSING_REPOS — mirroring the real API, which returns HTTP 200 with
#    `data.rN: null` plus a NOT_FOUND entry in `errors` for a repo it can't
#    resolve. $MOCK_GRAPHQL_HTTP forces a non-200 to exercise the fail-open path.
#    GraphQL requests are logged to their own file so the pagination-call
#    assertions stay independent of verification.
# gql-respond <response-file> <batch-log> — reads the posted GraphQL body on
# stdin and writes the mock response. Quoted heredoc: the jq program below is
# verbatim, so its regex escaping is not filtered through shell expansion.
cat > "$TEST_DIR/gql-respond" << 'RESPOND'
#!/bin/bash
set -euo pipefail
OUT="$1"
BATCH_LOG="$2"
REQ_URL="${3:-}"
BODY=$(cat)
# A host named in MOCK_UNSUPPORTED_HOSTS answers like a forge that isn't GitHub
# (a GitLab instance serves /api/graphql but has no `repository(owner:,name:)`
# field): HTTP 200, errors, no data. Nothing resolves for that host.
for _h in $(printf '%s' "${MOCK_UNSUPPORTED_HOSTS:-}" | tr ',' ' '); do
    [ -z "$_h" ] && continue
    case "$REQ_URL" in
        *"$_h"*)
            echo '{"errors":[{"message":"Field '"'"'repository'"'"' doesn'"'"'t exist on type '"'"'Query'"'"'"}]}' > "$OUT"
            echo 0 >> "$BATCH_LOG"
            exit 0
            ;;
    esac
done
# Pull every `rN: repository(owner: "o", name: "r")` alias out of the query and
# answer non-null for each, except the slugs named in MOCK_MISSING_REPOS. This
# mirrors the real API: HTTP 200, `data.rN: null`, and a NOT_FOUND entry in
# `errors` for anything it cannot resolve.
printf '%s' "$BODY" | jq -r --arg missing "${MOCK_MISSING_REPOS:-}" '
    ($missing | split(",") | map(select(length > 0))) as $gone
    | [ .query
        | scan("(r[0-9]+): repository\\(owner: \"([^\"]*)\", name: \"([^\"]*)\"\\)")
        | {alias: .[0], slug: (.[1] + "/" + .[2])} ] as $fields
    | ( { data: ( [ $fields[]
                    | {key: .alias,
                       value: (if (.slug | IN($gone[])) then null
                               else {id: ("R_" + .slug)} end)} ] | from_entries ),
          errors: [ $fields[] | select(.slug | IN($gone[]))
                    | {type: "NOT_FOUND", path: [.alias],
                       message: ("Could not resolve to a Repository with the name " + .slug)} ] }
        | if (.errors | length) == 0 then del(.errors) else . end
        | @json )
      + "\n" + ($fields | length | tostring)
' > "$OUT.raw"
head -1 "$OUT.raw" > "$OUT"
sed -n '2p' "$OUT.raw" >> "$BATCH_LOG"
rm -f "$OUT.raw"
RESPOND
chmod +x "$TEST_DIR/gql-respond"

cat > "$TEST_DIR/curl" << EOF
#!/bin/bash
WRITE_FILE=""
REQ_URL=""
while [ \$# -gt 0 ]; do
    case "\$1" in
        -o) WRITE_FILE="\$2"; shift 2 ;;
        -w) shift 2 ;;
        --data|--data-binary|--data-raw) shift 2 ;;
        -sS|-H|-X) shift 1; [ \$# -gt 0 ] && case "\$1" in -*) ;; *) shift 1 ;; esac ;;
        *) REQ_URL="\$1"; shift 1 ;;
    esac
done

case "\$REQ_URL" in
*/graphql)
    BODY=\$(cat)
    echo "\$REQ_URL" >> "$GQL_URLS"
    if [ -n "\${MOCK_GRAPHQL_HTTP:-}" ] && [ "\$MOCK_GRAPHQL_HTTP" != "200" ]; then
        echo '{"message":"mock failure"}' > "\$WRITE_FILE"
        echo "\$MOCK_GRAPHQL_HTTP"
        exit 0
    fi
    # A 200 carrying a non-JSON body — what a proxy/WAF error page looks like.
    if [ -n "\${MOCK_GRAPHQL_JUNK_BODY:-}" ]; then
        printf '<html><body>403 Forbidden</body></html>' > "\$WRITE_FILE"
        echo "200"
        exit 0
    fi
    # Delegate the response shaping to gql-respond (its own file, so its jq
    # program isn't run through this heredoc's escaping).
    printf '%s' "\$BODY" | "$TEST_DIR/gql-respond" "\$WRITE_FILE" "$GQL_BATCHES" "\$REQ_URL"
    echo "200"
    ;;
*)
    echo "\$REQ_URL" >> "$CURL_URLS"
    CALL_NUM=\$(wc -l < "$CURL_CALLS" 2>/dev/null || echo 0)
    echo "call \$((CALL_NUM + 1))" >> "$CURL_CALLS"
    if [ "\$CALL_NUM" -ge 4 ]; then
        echo '{"items":[],"pageInfo":{}}' > "\$WRITE_FILE"
    elif echo "\$REQ_URL" | grep -q 'cursor=CURSOR_P2'; then
        jq -c '{items: .items[5:], pageInfo: {}}' "\${MOCK_FIXTURE:-$FIXTURE}" > "\$WRITE_FILE"
    else
        jq -c '{items: .items[0:5], pageInfo: {nextCursor: "CURSOR_P2"}}' "\${MOCK_FIXTURE:-$FIXTURE}" > "\$WRITE_FILE"
    fi
    echo "200"
    ;;
esac
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
: > "$GQL_URLS"
: > "$GQL_BATCHES"

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

# 5. Nested hierarchy: spec.subdomainOf builds dotted domain keys, a System is
#    nested under its spec.domain, and a Component resolves its domain to the
#    full dotted path of its system. The fixture's commerce > checkout > orders
#    > fulfillment (System) > fulfillment-api (Component) chain exercises all
#    three, including entity-ref (domain:default/...) normalization.
CAPTURED_DOMAINS=$(jq -s 'add // {}' "$DOMAINS_OUT")
CAPTURED_COMPONENTS=$(jq -s 'add // {}' "$COMPONENTS_OUT")
for expect_dom in "commerce" "commerce.checkout" "commerce.checkout.orders" "commerce.checkout.orders.fulfillment"; do
    if echo "$CAPTURED_DOMAINS" | jq -e --arg k "$expect_dom" 'has($k)' >/dev/null; then :; else
        fail "expected nested domain key '$expect_dom' in .domains (subdomainOf / system nesting)"
    fi
done
FULFILL_DOMAIN=$(echo "$CAPTURED_COMPONENTS" | jq -r '.["github.com/acme/fulfillment-api"].domain // ""')
[ "$FULFILL_DOMAIN" = "commerce.checkout.orders.fulfillment" ] || \
    fail "fulfillment-api domain: expected 'commerce.checkout.orders.fulfillment', got '$FULFILL_DOMAIN'"

# --- 6. Structured include/exclude filters -------------------------------
# Re-run the cataloger against the same fixture with each filter set and assert
# the resulting component key set (github.com/ prefix stripped, sorted, joined).
# The 5 baseline annotated components and their relevant fields:
#   acme/payment-api        type=service  lifecycle=production  system=payments   -> platform.payments.payments
#   acme/web-app            type=website  lifecycle=production  system=storefront -> storefront
#   acme/payment-api-proto  type=grpc     lifecycle=production  (no system/domain)-> ""
#   acme/payments-db-iac    type=database (NO lifecycle)        system=payments   -> platform.payments.payments
#   acme/fulfillment-api    type=service  lifecycle=production  system=fulfillment-> commerce.checkout.orders.fulfillment
echo ""
echo "=== Filter scenarios ==="

# filter_keys inc_types exc_types inc_life exc_life inc_dom exc_dom inc_sys exc_sys
# -> echoes sorted, comma-joined component keys with the github.com/ prefix stripped.
filter_keys() {
    : > "$COMPONENTS_OUT"; : > "$DOMAINS_OUT"; : > "$CURL_CALLS"; : > "$CURL_URLS"
    if ! LUNAR_VAR_INCLUDE_TYPES="$1" LUNAR_VAR_EXCLUDE_TYPES="$2" \
         LUNAR_VAR_INCLUDE_LIFECYCLES="$3" LUNAR_VAR_EXCLUDE_LIFECYCLES="$4" \
         LUNAR_VAR_INCLUDE_DOMAINS="$5" LUNAR_VAR_EXCLUDE_DOMAINS="$6" \
         LUNAR_VAR_INCLUDE_SYSTEMS="$7" LUNAR_VAR_EXCLUDE_SYSTEMS="$8" \
         "$SCRIPT_DIR/main.sh" > "$TEST_DIR/filter.out" 2>&1; then
        echo "__MAINSH_FAILED__"; return
    fi
    jq -rs 'add // {} | keys | map(sub("^github.com/"; "")) | sort | join(",")' "$COMPONENTS_OUT"
}

check_filter() { # $1=label $2=expected $3=got
    if [ "$3" = "$2" ]; then
        echo "  ok: $1 -> {$3}"
    else
        fail "[$1] expected components {$2}, got {$3}"
    fi
}

check_filter "include_types=service" \
    "acme/fulfillment-api,acme/payment-api" \
    "$(filter_keys service '' '' '' '' '' '' '')"

check_filter "exclude_types=database" \
    "acme/fulfillment-api,acme/payment-api,acme/payment-api-proto,acme/web-app" \
    "$(filter_keys '' database '' '' '' '' '' '')"

# exclude wins over include: database is in BOTH lists -> dropped.
check_filter "include=service,database + exclude=database (exclude wins)" \
    "acme/fulfillment-api,acme/payment-api" \
    "$(filter_keys 'service,database' database '' '' '' '' '' '')"

# attribute-absent passes: payments-db-iac (Resource, no lifecycle) survives a
# lifecycle allowlist -> all 5 remain.
check_filter "include_lifecycles=production (Resource w/o lifecycle passes)" \
    "acme/fulfillment-api,acme/payment-api,acme/payment-api-proto,acme/payments-db-iac,acme/web-app" \
    "$(filter_keys '' '' production '' '' '' '' '')"

check_filter "include_types=SERVICE (case-insensitive)" \
    "acme/fulfillment-api,acme/payment-api" \
    "$(filter_keys SERVICE '' '' '' '' '' '' '')"

# domain membership + dotted-prefix: only the commerce subtree; the no-domain
# grpc API is not a member -> excluded.
check_filter "include_domains=commerce (prefix match, no-domain excluded)" \
    "acme/fulfillment-api" \
    "$(filter_keys '' '' '' '' commerce '' '' '')"

# exclude_domains drops the platform.payments subtree; no-domain component is
# unaffected by an exclude (kept).
check_filter "exclude_domains=platform.payments" \
    "acme/fulfillment-api,acme/payment-api-proto,acme/web-app" \
    "$(filter_keys '' '' '' '' '' platform.payments '' '')"

check_filter "include_systems=payments (exact bare-name match)" \
    "acme/payment-api,acme/payments-db-iac" \
    "$(filter_keys '' '' '' '' '' '' payments '')"

# Domains are never touched by component filters — still all 7 under a filter.
: > "$COMPONENTS_OUT"; : > "$DOMAINS_OUT"; : > "$CURL_CALLS"; : > "$CURL_URLS"
LUNAR_VAR_INCLUDE_TYPES="service" "$SCRIPT_DIR/main.sh" >/dev/null 2>&1 || true
DOMAINS_UNDER_FILTER=$(jq -s 'add // {} | keys | length' "$DOMAINS_OUT")
[ "$DOMAINS_UNDER_FILTER" -eq "$EXPECTED_DOMAINS" ] || \
    fail "domains must be unaffected by component filters: expected $EXPECTED_DOMAINS, got $DOMAINS_UNDER_FILTER"

# --- 7. Repo-existence verification (verify_repos) ------------------------
# The fixture's 5 annotated components resolve to 5 distinct acme/* repos. Each
# scenario re-runs the cataloger and reports the surviving component keys plus
# how many GraphQL requests were issued, so both the filtering and the request
# batching are asserted.
echo ""
echo "=== verify_repos scenarios ==="

# verify_run <verify_repos> <gh_token> <missing_csv> <batch_size> <http_code> [extra VAR=val...]
# -> sets VR_KEYS (sorted component keys, prefix stripped), VR_GQL (request count),
#    VR_OUT (path to the run log).
verify_run() {
    local verify="$1" token="$2" missing="$3" batch="$4" http="$5"; shift 5
    : > "$COMPONENTS_OUT"; : > "$DOMAINS_OUT"; : > "$CURL_CALLS"; : > "$CURL_URLS"
    : > "$GQL_URLS"; : > "$GQL_BATCHES"
    VR_OUT="$TEST_DIR/verify.out"
    env "$@" \
        LUNAR_VAR_VERIFY_REPOS="$verify" \
        LUNAR_SECRET_GH_TOKEN="$token" \
        MOCK_MISSING_REPOS="$missing" \
        MOCK_GRAPHQL_HTTP="$http" \
        VERIFY_BATCH_SIZE="$batch" \
        "$SCRIPT_DIR/main.sh" > "$VR_OUT" 2>&1 || true
    VR_KEYS=$(jq -rs 'add // {} | keys | map(sub("^github.com/"; "")) | sort | join(",")' "$COMPONENTS_OUT")
    VR_GQL=$(grep -c . "$GQL_URLS" || true)
}

ALL_FIVE="acme/fulfillment-api,acme/payment-api,acme/payment-api-proto,acme/payments-db-iac,acme/web-app"

check_verify() { # $1=label $2=expected keys $3=got keys
    if [ "$3" = "$2" ]; then
        echo "  ok: $1"
    else
        fail "[$1] expected components {$2}, got {$3}"
    fi
}

# (a) A repo that doesn't exist is dropped; the rest are written untouched.
verify_run true mock-gh-token "acme/payment-api-proto" 100 200
check_verify "missing repo dropped" \
    "acme/fulfillment-api,acme/payment-api,acme/payments-db-iac,acme/web-app" "$VR_KEYS"
[ "$VR_GQL" -eq 1 ] || fail "expected 1 GraphQL request for 5 repos at batch=100, got $VR_GQL"
grep -q "github.com/acme/payment-api-proto" "$VR_OUT" || \
    fail "the dropped component id must be named in the log (operator fixes it in Backstage)"
grep -q "Repo verification dropped 1 of 5 component(s)" "$VR_OUT" || \
    fail "expected a 'dropped 1 of 5' summary line; got: $(grep -i 'verification' "$VR_OUT" | tr '\n' '|')"

# Negative control: with nothing missing, the same run keeps all five. Without
# this, (a) would also pass if the code dropped components for the wrong reason.
verify_run true mock-gh-token "" 100 200
check_verify "nothing missing -> all kept" "$ALL_FIVE" "$VR_KEYS"

# (b) No GH_TOKEN: unchanged output, no GraphQL call, and a warning that says so.
verify_run true "" "acme/payment-api-proto" 100 200
check_verify "no token -> writes everything (fail open)" "$ALL_FIVE" "$VR_KEYS"
[ "$VR_GQL" -eq 0 ] || fail "expected no GraphQL request without a token, got $VR_GQL"
grep -q "no GH_TOKEN secret is set" "$VR_OUT" || \
    fail "expected a warning naming the missing GH_TOKEN secret"

# (c) verify_repos off: no verification at all, even with a token.
verify_run false mock-gh-token "acme/payment-api-proto" 100 200
check_verify "verify_repos=false -> no filtering" "$ALL_FIVE" "$VR_KEYS"
[ "$VR_GQL" -eq 0 ] || fail "expected no GraphQL request when verify_repos=false, got $VR_GQL"

# (d) Every repo missing is a token/host misconfiguration, not a catalog where
#     every entry is stale — must not empty the catalog.
verify_run true mock-gh-token "$ALL_FIVE" 100 200
check_verify "all missing -> inconclusive, nothing dropped" "$ALL_FIVE" "$VR_KEYS"
grep -q "inconclusive" "$VR_OUT" || fail "expected an 'inconclusive' warning when no repo resolves"

# (e) A non-200 from GitHub must not shrink the catalog either.
verify_run true mock-gh-token "acme/payment-api-proto" 100 503
check_verify "HTTP 503 -> fail open" "$ALL_FIVE" "$VR_KEYS"
grep -q "verification request failed (HTTP 503)" "$VR_OUT" || \
    fail "expected the HTTP failure to be reported"

# (e2) A 200 with a non-JSON body (proxy/WAF error page) must fail open too, not
#      abort the run — jq exits non-zero on it and `set -e` would kill the whole
#      cataloger. This is the regression that shipped in the first cut.
verify_run true mock-gh-token "acme/payment-api-proto" 100 200 MOCK_GRAPHQL_JUNK_BODY=1
check_verify "200 + junk body -> fail open" "$ALL_FIVE" "$VR_KEYS"
grep -q "could not parse .* response" "$VR_OUT" || \
    fail "expected the unparseable-response warning"
grep -q "Backstage sync complete" "$VR_OUT" || \
    fail "an unparseable verification response must not abort the run"

# (f) Batching: 5 repos at batch=2 is 3 requests. This is the assertion that
#     keeps the check from regressing to one request per component — at a large
#     catalog that difference is the whole GitHub rate-limit budget.
verify_run true mock-gh-token "acme/payment-api-proto" 2 200
check_verify "batch=2 still drops only the missing repo" \
    "acme/fulfillment-api,acme/payment-api,acme/payments-db-iac,acme/web-app" "$VR_KEYS"
[ "$VR_GQL" -eq 3 ] || fail "expected ceil(5/2)=3 GraphQL requests at batch=2, got $VR_GQL"
BATCH_SIZES=$(sort "$GQL_BATCHES" | tr '\n' ',')
[ "$BATCH_SIZES" = "1,2,2," ] || \
    fail "expected batches of 2,2,1 repos per request; got sizes {$BATCH_SIZES}"

# (g) Host comes from the component id, with NO extra config: a GHES-prefixed
#     catalog is checked against https://<host>/api/graphql, not github.com.
verify_run true mock-gh-token "acme/payment-api-proto" 100 200 LUNAR_VAR_COMPONENT_ID_PREFIX="ghes.example.com/"
GHES_KEYS=$(jq -rs 'add // {} | keys | map(sub("^ghes.example.com/"; "")) | sort | join(",")' "$COMPONENTS_OUT")
check_verify "GHES id -> verified, zero config" \
    "acme/fulfillment-api,acme/payment-api,acme/payments-db-iac,acme/web-app" "$GHES_KEYS"
[ "$(head -1 "$GQL_URLS")" = "https://ghes.example.com/api/graphql" ] || \
    fail "GHES endpoint should be derived from the id as https://ghes.example.com/api/graphql, got '$(head -1 "$GQL_URLS")'"

# --- Multi-host: one catalog spanning github.com and a GHES host -------------
# Uses its own fixture whose annotation values already carry the host, with an
# empty component_id_prefix, so the ids are genuinely mixed-host.
MULTI_FIXTURE="$SCRIPT_DIR/sample-catalog-multihost.json"

multi_run() { # $1=missing csv  $2=unsupported hosts csv
    : > "$COMPONENTS_OUT"; : > "$DOMAINS_OUT"; : > "$CURL_CALLS"; : > "$CURL_URLS"
    : > "$GQL_URLS"; : > "$GQL_BATCHES"
    VR_OUT="$TEST_DIR/multi.out"
    env MOCK_FIXTURE="$MULTI_FIXTURE" \
        MOCK_MISSING_REPOS="$1" \
        MOCK_UNSUPPORTED_HOSTS="$2" \
        LUNAR_VAR_VERIFY_REPOS=true \
        LUNAR_SECRET_GH_TOKEN=mock-gh-token \
        LUNAR_VAR_COMPONENT_ID_PREFIX="" \
        "$SCRIPT_DIR/main.sh" > "$VR_OUT" 2>&1 || true
    MULTI_KEYS=$(jq -rs 'add // {} | keys | sort | join(",")' "$COMPONENTS_OUT")
    MULTI_HOSTS=$(sort -u "$GQL_URLS" | tr '\n' ',')
}

ALL_FOUR="github.com/acme/payments,github.com/acme/retired,ghes.example.com/corp/billing,ghes.example.com/corp/ghost"
ALL_FOUR=$(printf '%s' "$ALL_FOUR" | tr ',' '\n' | sort | tr '\n' ',' | sed 's/,$//')

# (h) Both hosts get verified, each at its own endpoint, and the absent repo on
#     EACH host is dropped independently.
multi_run "acme/retired,corp/ghost" ""
check_verify "multi-host: both hosts filtered" \
    "ghes.example.com/corp/billing,github.com/acme/payments" "$MULTI_KEYS"
[ "$MULTI_HOSTS" = "https://api.github.com/graphql,https://ghes.example.com/api/graphql," ] || \
    fail "expected both host endpoints to be hit; got {$MULTI_HOSTS}"

# (i) Per-host isolation — the point of deriving the host per component. A host
#     that isn't GitHub (GitLab serves /api/graphql but has no repository()
#     field) resolves nothing, so ITS components are left alone while github.com
#     is still filtered normally. Without isolation this would either drop every
#     GHES component or fail open across the whole catalog.
multi_run "acme/retired,corp/ghost" "ghes.example.com"
check_verify "non-GitHub host isolated: its components kept, github.com still filtered" \
    "ghes.example.com/corp/billing,ghes.example.com/corp/ghost,github.com/acme/payments" "$MULTI_KEYS"
grep -q "ghes.example.com is inconclusive" "$VR_OUT" || \
    fail "expected an inconclusive warning naming the unsupported host"
grep -q "verification supports GitHub hosts only" "$VR_OUT" || \
    fail "the inconclusive warning should say verification is GitHub-only"

# (j) An id with no host segment (empty prefix + bare owner/repo) is not
#     addressable, so it is left alone rather than guessed at.
NOHOST_KEPT=$(echo '{"acme/payments":{"tags":[]},"github.com/acme/payments":{"tags":[]}}' | jq \
    --rawfile present <(printf 'github.com/acme/payments\n') \
    --rawfile checked <(printf 'github.com\n') '
    ($present | split("\n") | map(select(length > 0))) as $ok
    | ($checked | split("\n") | map(select(length > 0))) as $hosts
    | with_entries((.key | split("/")) as $p
        | select(($p|length) < 3 or $p[0]=="" or $p[1]=="" or $p[2]==""
                 or (($p[0] | IN($hosts[])) | not)
                 or (($p[0:3] | join("/")) | IN($ok[]))))' | jq -r 'keys | sort | join(",")')
[ "$NOHOST_KEPT" = "acme/payments,github.com/acme/payments" ] || \
    fail "a hostless id must be left alone, not dropped; got {$NOHOST_KEPT}"

# (i) Monorepo-style ids (<owner>/<repo>/<subdir>) resolve to their backing repo,
#     so a subcomponent follows its repo's verdict rather than being treated as
#     an unverifiable id.
: > "$COMPONENTS_OUT"; : > "$GQL_URLS"
SUBDIR_IN='{"github.com/acme/payment-api":{"tags":[]},"github.com/acme/payment-api/services/billing":{"tags":[]},"github.com/acme/gone/services/void":{"tags":[]}}'
SUBDIR_KEPT=$(echo "$SUBDIR_IN" | jq --arg prefix "github.com/" --rawfile present <(printf 'acme/payment-api\n') '
    ($present | split("\n") | map(select(length > 0))) as $ok
    | with_entries(
        (.key | ltrimstr($prefix) | split("/")) as $parts
        | select(($parts | length) < 2 or $parts[0] == "" or $parts[1] == ""
                 or (($parts[0] + "/" + $parts[1]) | IN($ok[]))))' | jq -r 'keys | sort | join(",")')
[ "$SUBDIR_KEPT" = "github.com/acme/payment-api,github.com/acme/payment-api/services/billing" ] || \
    fail "monorepo subcomponent should follow its backing repo's verdict; got {$SUBDIR_KEPT}"

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo "PASS: 2-page cursor pagination, api_path_prefix='${NP:-<none>}', $COMPONENTS_GOT components + $DOMAINS_GOT domains, nested subdomainOf/system paths, include/exclude filters (type/lifecycle/domain/system), and verify_repos (drop/keep, fail-open paths, GHES endpoint, batching) verified"
else
    echo "TEST FAILED" >&2
    exit 1
fi
