#!/bin/bash
#
# Local offline test for the Backstage collector. Mocks `curl` (against the
# Backstage catalog by-name API) and `lunar` (capturing the collected
# `.catalog.native.backstage` write) so the collector can be exercised
# end-to-end — through the real `yq`/`python3` pipeline — without network
# access. Covers two things:
#   1. Multi-document parsing/linting (multiple entities separated by `---`).
#      This is the path the alpine CI unit tests can't reach (no yq there).
#   2. The optional referential-integrity feature.
#
# The mock curl returns an HTTP status keyed off the requested entity name:
#   typo*  -> 404 (definitive miss)      five -> 502 (transient 5xx)
#   boom   -> connection error (exit 7)  else -> 200 (exists)
#
# Run: ./test-local.sh   (needs bash, jq, yq)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

MOCK="$TEST_DIR/bin"
mkdir -p "$MOCK"

# Exported: the mock curl below reads it from its own environment.
export CURL_LOG="$TEST_DIR/curl.log"

# --- Mock curl ------------------------------------------------------------
# Logs every invocation (so tests can assert which auth flags were passed),
# then answers three families of request:
#   * AWS metadata endpoints (IMDSv2 / ECS container creds) -> always
#     unreachable, so the credential chain falls through deterministically
#     rather than depending on whatever the host VM happens to expose.
#   * STS AssumeRoleWithWebIdentity -> mock credentials when MOCK_STS=1.
#     Matched against the whole arg list, not the last arg: the STS call puts
#     --data-urlencode pairs *after* the URL.
#   * the Backstage by-name API -> an http_code keyed off the entity name.
cat > "$MOCK/curl" << 'EOF'
#!/bin/bash
[ -n "${CURL_LOG:-}" ] && printf '%s\n' "$*" >> "$CURL_LOG"

args="$*"
case "$args" in
  *169.254.169.254*|*169.254.170.2*) exit 7 ;;
  *sts.*amazonaws.com*)
    if [ "${MOCK_STS:-0}" = "1" ]; then
      printf '%s' '<AssumeRoleWithWebIdentityResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/"><AssumeRoleWithWebIdentityResult><Credentials><AccessKeyId>ASIAMOCKKEY</AccessKeyId><SecretAccessKey>mocksecret</SecretAccessKey><SessionToken>mocksessiontoken</SessionToken></Credentials></AssumeRoleWithWebIdentityResult></AssumeRoleWithWebIdentityResponse>'
      exit 0
    fi
    exit 7 ;;
esac

url="${@: -1}"

# Body of a resolved entity. A System carries `spec.domain`, so the
# component -> system -> that system's domain hop has something to follow. The
# domain it names is keyed off the system name, mirroring the status convention
# above, and is then resolved through the same mock:
#   *-nodomain -> System belonging to no domain (no spec.domain at all)
#   dangling*  -> spec.domain: typo-domain, which resolves 404 -> exists:false
#   else       -> spec.domain: payments, which resolves 200 -> exists:true
# `namespace` is echoed back from the request so a cross-namespace hop (a bare
# spec.domain on a System in another namespace) can be asserted.
mock_entity() {
  local kind="$1" ns="$2" ename="$3" dom=""
  if [ "$kind" = "system" ]; then
    case "$ename" in
      *-nodomain) dom="" ;;
      dangling*)  dom="typo-domain" ;;
      *)          dom="payments" ;;
    esac
  fi
  if [ -n "$dom" ]; then
    printf '{"kind":"%s","metadata":{"name":"%s","namespace":"%s"},"spec":{"domain":"%s"}}' \
      "$kind" "$ename" "$ns" "$dom"
  else
    printf '{"kind":"%s","metadata":{"name":"%s","namespace":"%s"},"spec":{}}' \
      "$kind" "$ename" "$ns"
  fi
}

# by-query: existence lives in the body, so answer with a real by-query
# envelope plus the trailing http_code that `-w '\n%{http_code}'` appends.
# The name is read back out of the filter, which is also how the tests assert
# the filter was built (and escaped) correctly.
case "$url" in
  */catalog/entities/by-query\?*)
    qname="${url##*metadata.name=}"
    qname="${qname%%&*}"
    qkind="${url##*filter=kind=}"
    qkind="${qkind%%,*}"
    qns="${url##*metadata.namespace=}"
    qns="${qns%%,*}"
    case "$qname" in
      boom)  exit 7 ;;
      five)  printf '%s\n502' '{"message":"bad gateway"}'; exit 0 ;;
      # A gateway answering 200 with an SSO login page instead of JSON. Must
      # NOT be read as "the entity does not exist".
      login) printf '%s\n200' '<html><body>SSO login</body></html>'; exit 0 ;;
      # A 200 of the wrong shape (no .items array) — also not a miss.
      noitems) printf '%s\n200' '{"totalItems":0}'; exit 0 ;;
      typo*) printf '%s\n200' '{"items":[],"totalItems":0,"pageInfo":{}}'; exit 0 ;;
      *)     printf '%s\n200' "{\"items\":[$(mock_entity "$qkind" "$qns" "$qname")],\"totalItems\":1,\"pageInfo\":{}}"; exit 0 ;;
    esac ;;
esac

# by-name: the status is the existence answer, but the collector also reads the
# body off this endpoint (for the system -> domain hop), so emit both in the
# `<body>\n<http_code>` shape that `-w '\n%{http_code}'` actually produces.
rest="${url##*/by-name/}"
kind="${rest%%/*}"
nsname="${rest#*/}"
ns="${nsname%%/*}"
name="${nsname#*/}"
case "$name" in
  boom)  exit 7 ;;
  five)  printf '%s\n502' '{"message":"bad gateway"}'; exit 0 ;;
  typo*) printf '%s\n404' '{}'; exit 0 ;;
  *)     printf '%s\n200' "$(mock_entity "$kind" "$ns" "$name")"; exit 0 ;;
esac
EOF
chmod +x "$MOCK/curl"

# --- Mock lunar: capture stdin (the collected JSON) -----------------------
printf '#!/bin/bash\ncat\n' > "$MOCK/lunar"
chmod +x "$MOCK/lunar"

# Run main.sh in a fresh workdir with a crafted catalog-info.yaml, echoing the
# collected `.refs` object (or `null` when none was written).
# run_full "EXTRA_ENV=..." <domain> <system> <url> [ns]
#   Emits the FULL collected `.catalog.native.backstage` object, so a test can
#   assert on `.refs` *and* on the parse/lint fields in the same run — which is
#   what the degrade-not-fail cases need. $extra is intentionally unquoted at
#   the call site so simple KEY=VALUE pairs word-split into env assignments.
run_full() {
  local extra="$1" domain="$2" system="$3" url="$4" ns="${5:-}"
  local wd="$TEST_DIR/wd"
  rm -rf "$wd"; mkdir -p "$wd"
  {
    echo "apiVersion: backstage.io/v1alpha1"
    echo "kind: Component"
    echo "metadata:"
    echo "  name: demo"
    [ -n "$ns" ] && echo "  namespace: $ns"
    echo "spec:"
    echo "  type: service"
    echo "  owner: team-demo"
    echo "  lifecycle: production"
    [ -n "$domain" ] && echo "  domain: $domain"
    [ -n "$system" ] && echo "  system: $system"
  } > "$wd/catalog-info.yaml"
  # shellcheck disable=SC2086  # $extra must word-split into env assignments
  ( cd "$wd" \
    && env PATH="$MOCK:$PATH" \
       LUNAR_VAR_PATHS="catalog-info.yaml,catalog-info.yml" \
       LUNAR_VAR_BACKSTAGE_URL="$url" \
       $extra \
       bash "$SCRIPT_DIR/main.sh" )
}

run() {
  run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=test-token" "$1" "$2" "$3" "${4:-}" | jq -c '.refs'
}

# Run main.sh against a catalog-info.yaml whose contents are supplied on stdin
# (no backstage_url, so no network / .refs), echoing the full collected
# `.catalog.native.backstage` object.
run_collect() {
  local wd="$TEST_DIR/wd"
  rm -rf "$wd"; mkdir -p "$wd"
  cat > "$wd/catalog-info.yaml"
  ( cd "$wd" \
    && PATH="$MOCK:$PATH" \
       LUNAR_VAR_PATHS="catalog-info.yaml,catalog-info.yml" \
       LUNAR_VAR_BACKSTAGE_URL="" \
       bash "$SCRIPT_DIR/main.sh" )
}

# Same as run_collect, but with referential integrity enabled against $1 — for
# catalog files whose shape run_full can't express (it always writes a
# `kind: Component`).
run_collect_url() {
  local url="$1"
  local wd="$TEST_DIR/wd"
  rm -rf "$wd"; mkdir -p "$wd"
  cat > "$wd/catalog-info.yaml"
  ( cd "$wd" \
    && PATH="$MOCK:$PATH" \
       LUNAR_VAR_PATHS="catalog-info.yaml,catalog-info.yml" \
       LUNAR_VAR_BACKSTAGE_URL="$url" \
       LUNAR_SECRET_BACKSTAGE_TOKEN="test-token" \
       bash "$SCRIPT_DIR/main.sh" )
}

FAILS=0
assert_eq() {
  local desc="$1" got="$2" want="$3"
  if [ "$got" = "$want" ]; then
    echo "  ok: $desc"
  else
    echo "  FAIL: $desc"
    echo "    want: $want"
    echo "    got:  $got"
    FAILS=$((FAILS + 1))
  fi
}

echo "Backstage collector multi-document parse/lint tests:"

# A legal Component + API file (the reported bug) must parse cleanly: valid,
# both entities captured, and the Component hoisted as the primary so the
# owner/lifecycle/system policies read its spec.
MULTI=$(run_collect < "$SCRIPT_DIR/test/fixtures/multi-doc-catalog-info.yaml")
assert_eq "multi-doc valid overall" \
  "$(echo "$MULTI" | jq -c '.valid')" 'true'
assert_eq "multi-doc captures every entity" \
  "$(echo "$MULTI" | jq -c '[.entities[].kind]')" '["Component","API"]'
assert_eq "multi-doc hoists the Component as primary" \
  "$(echo "$MULTI" | jq -c '{kind, owner:.spec.owner, system:.spec.system}')" \
  '{"kind":"Component","owner":"team-payments","system":"payment-platform"}'

# One invalid entity fails the whole file, and the error names which document.
BAD=$(run_collect <<'EOF'
apiVersion: backstage.io/v1alpha1
kind: Component
metadata: {name: good-comp}
spec: {owner: t, lifecycle: production}
---
apiVersion: backstage.io/v1alpha1
kind: API
metadata:
  name: bad-api
  tags: ["hosting/internal"]
spec: {owner: t}
EOF
)
assert_eq "multi-doc with a bad entity is invalid" \
  "$(echo "$BAD" | jq -c '.valid')" 'false'
assert_eq "error locates the offending document" \
  "$(echo "$BAD" | jq -r '.errors[0].message' | grep -c "document 2 (API 'bad-api')")" '1'

echo "Backstage collector referential-integrity tests:"

assert_eq "domain exists (200) + system miss (404)" \
  "$(run payments typo-platform http://fake:7007)" \
  '{"checked":true,"domain":{"name":"payments","exists":true},"system":{"name":"typo-platform","exists":false}}'

assert_eq "transient 5xx -> error marker, not exists" \
  "$(run '' five http://fake:7007 | jq -c '.system')" \
  '{"name":"five","error":"HTTP 502"}'

assert_eq "connection error -> error marker" \
  "$(run boom '' http://fake:7007 | jq -c '.domain')" \
  '{"name":"boom","error":"request failed (curl exit 7)"}'

assert_eq "qualified ns/name ref keeps its own namespace" \
  "$(run prod/payments '' http://fake:7007 compns | jq -c '.domain')" \
  '{"name":"prod/payments","exists":true}'

assert_eq "unconfigured (no backstage_url) writes no .refs" \
  "$(run payments payment-platform '')" \
  'null'

STATIC_KEYS="LUNAR_SECRET_AWS_ACCESS_KEY_ID=AKIATEST LUNAR_SECRET_AWS_SECRET_ACCESS_KEY=secret123"

echo "Backstage collector api_path_prefix tests:"

# Default is the standard Backstage layout.
: > "$CURL_LOG"
run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t" payments '' http://fake:7007 >/dev/null
assert_eq "default prefix hits /api/catalog/entities" \
  "$(grep -c 'http://fake:7007/api/catalog/entities/by-name/domain/default/payments' "$CURL_LOG")" '1'

# The case that matters for sigv4: an API gateway that strips the /api hop.
# `-` vs `:-` — an explicitly empty value must survive, not fall back to /api.
: > "$CURL_LOG"
run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t LUNAR_VAR_API_PATH_PREFIX=" payments '' http://fake:7007 >/dev/null
assert_eq "empty prefix mounts the catalog API at the root" \
  "$(grep -c 'http://fake:7007/catalog/entities/by-name/domain/default/payments' "$CURL_LOG")" '1'
assert_eq "empty prefix does NOT fall back to /api" \
  "$(grep -c '/api/catalog' "$CURL_LOG" || true)" '0'

# Normalization: `api`, `/api/` and `/api` are equivalent.
for form in "api" "/api/"; do
  : > "$CURL_LOG"
  run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t LUNAR_VAR_API_PATH_PREFIX=$form" payments '' http://fake:7007 >/dev/null
  assert_eq "prefix '$form' normalizes to /api" \
    "$(grep -c 'http://fake:7007/api/catalog/entities/by-name/domain/default/payments' "$CURL_LOG")" '1'
done

# A custom gateway stage prefix passes through.
: > "$CURL_LOG"
run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t LUNAR_VAR_API_PATH_PREFIX=/prod/api" payments '' http://fake:7007 >/dev/null
assert_eq "custom prefix is used verbatim" \
  "$(grep -c 'http://fake:7007/prod/api/catalog/entities/by-name/domain/default/payments' "$CURL_LOG")" '1'

# The gateway case end-to-end: sigv4 + a root-mounted catalog API must sign the
# *rewritten* path, not the /api one. This is the combination Fry flagged.
: > "$CURL_LOG"
SIGV4_ROOT=$(run_full "LUNAR_VAR_AUTH_MODE=sigv4 LUNAR_VAR_AWS_REGION=us-east-1 LUNAR_VAR_API_PATH_PREFIX= $STATIC_KEYS" \
  payments '' http://fake:7007 | jq -c '.refs.domain')
assert_eq "sigv4 + root-mounted API resolves the ref" \
  "$SIGV4_ROOT" '{"name":"payments","exists":true}'
assert_eq "sigv4 + root-mounted API signs the root path" \
  "$(grep -c 'http://fake:7007/catalog/entities/by-name/domain/default/payments' "$CURL_LOG")" '1'

echo "Backstage collector auth-mode (bearer / sigv4) tests:"

# Negative control: the default bearer path must be untouched by the sigv4
# work — the token still goes out as an Authorization header, and NO SigV4
# flags are added. Without this, a sigv4 regression could hide behind a
# green sigv4 test.
: > "$CURL_LOG"
BEARER_REFS=$(run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=test-token" payments '' http://fake:7007 | jq -c '.refs.domain')
assert_eq "bearer (default) still resolves refs" \
  "$BEARER_REFS" '{"name":"payments","exists":true}'
assert_eq "bearer sends the Authorization header" \
  "$(grep -c 'Authorization: Bearer test-token' "$CURL_LOG")" '1'
assert_eq "bearer sends NO sigv4 flags" \
  "$(grep -c 'aws-sigv4' "$CURL_LOG" || true)" '0'

# sigv4 happy path via the static-key escape hatch (chain step 4): refs
# resolve exactly as under bearer, and the signing flags are on the wire.
: > "$CURL_LOG"
SIGV4_REFS=$(run_full "LUNAR_VAR_AUTH_MODE=sigv4 LUNAR_VAR_AWS_REGION=us-east-1 $STATIC_KEYS" \
  payments typo-platform http://fake:7007 | jq -c '.refs')
assert_eq "sigv4 resolves refs (200 exists / 404 miss) like bearer" \
  "$SIGV4_REFS" \
  '{"checked":true,"domain":{"name":"payments","exists":true},"system":{"name":"typo-platform","exists":false}}'
assert_eq "sigv4 passes the signing flags with the right scope" \
  "$(grep -c -- '--aws-sigv4 aws:amz:us-east-1:execute-api' "$CURL_LOG")" '2'
assert_eq "sigv4 sends no Bearer header" \
  "$(grep -c 'Authorization: Bearer' "$CURL_LOG" || true)" '0'

# aws_service is overridable for non-API-Gateway fronting.
: > "$CURL_LOG"
run_full "LUNAR_VAR_AUTH_MODE=sigv4 LUNAR_VAR_AWS_REGION=eu-west-2 LUNAR_VAR_AWS_SERVICE=lambda $STATIC_KEYS" \
  payments '' http://fake:7007 >/dev/null
assert_eq "aws_service override reaches the signature scope" \
  "$(grep -c -- '--aws-sigv4 aws:amz:eu-west-2:lambda' "$CURL_LOG")" '1'

# Temporary credentials must also send the session-token header.
: > "$CURL_LOG"
run_full "LUNAR_VAR_AUTH_MODE=sigv4 LUNAR_VAR_AWS_REGION=us-east-1 $STATIC_KEYS LUNAR_SECRET_AWS_SESSION_TOKEN=tmptok" \
  payments '' http://fake:7007 >/dev/null
assert_eq "static session token is sent as x-amz-security-token" \
  "$(grep -c 'x-amz-security-token: tmptok' "$CURL_LOG")" '1'

# IRSA (chain step 1) wins over the static keys and self-refreshes.
: > "$CURL_LOG"
echo "mock-web-identity-token" > "$TEST_DIR/wit"
run_full "LUNAR_VAR_AUTH_MODE=sigv4 LUNAR_VAR_AWS_REGION=us-east-1 $STATIC_KEYS MOCK_STS=1 AWS_ROLE_ARN=arn:aws:iam::123456789012:role/r AWS_WEB_IDENTITY_TOKEN_FILE=$TEST_DIR/wit" \
  payments '' http://fake:7007 >/dev/null
assert_eq "IRSA web-identity creds take precedence over static keys" \
  "$(grep -c -- '--user ASIAMOCKKEY:mocksecret' "$CURL_LOG")" '1'
assert_eq "IRSA session token is sent" \
  "$(grep -c 'x-amz-security-token: mocksessiontoken' "$CURL_LOG")" '1'

echo "Backstage collector ref_lookup (by-name / by-query) tests:"

# Negative control first: an unset ref_lookup must keep hitting by-name and
# must NOT start sending by-query traffic. Without this a by-query regression
# could hide behind green by-query tests.
: > "$CURL_LOG"
run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t" payments '' http://fake:7007 >/dev/null
assert_eq "default ref_lookup still uses by-name" \
  "$(grep -c '/catalog/entities/by-name/domain/default/payments' "$CURL_LOG")" '1'
assert_eq "default ref_lookup sends no by-query request" \
  "$(grep -c 'by-query' "$CURL_LOG" || true)" '0'

# by-query resolves both outcomes from the BODY, not the status: the mock
# answers 200 for every by-query request, so a miss can only come from an
# empty `.items`. Same `.refs` shape as by-name — policies are unaffected.
: > "$CURL_LOG"
BQ_REFS=$(run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t LUNAR_VAR_REF_LOOKUP=by-query" \
  payments typo-platform http://fake:7007 | jq -c '.refs')
assert_eq "by-query resolves exists (non-empty .items) + miss (empty .items)" \
  "$BQ_REFS" \
  '{"checked":true,"domain":{"name":"payments","exists":true},"system":{"name":"typo-platform","exists":false}}'
assert_eq "by-query calls the by-query endpoint with the entity filter" \
  "$(grep -c 'http://fake:7007/api/catalog/entities/by-query?limit=1&filter=kind=domain,metadata.namespace=default,metadata.name=payments' "$CURL_LOG")" '1'
assert_eq "by-query filters on each reference's own kind" \
  "$(grep -c 'filter=kind=system,metadata.namespace=default,metadata.name=typo-platform' "$CURL_LOG")" '1'
assert_eq "by-query sends no by-name request" \
  "$(grep -c 'by-name' "$CURL_LOG" || true)" '0'

# A qualified ns/name ref carries its own namespace into the filter.
: > "$CURL_LOG"
assert_eq "by-query keeps a qualified ref's own namespace" \
  "$(run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t LUNAR_VAR_REF_LOOKUP=by-query" prod/payments '' http://fake:7007 compns | jq -c '.refs.domain')" \
  '{"name":"prod/payments","exists":true}'
assert_eq "by-query puts that namespace in the filter, not the component's" \
  "$(grep -c 'metadata.namespace=prod,metadata.name=payments' "$CURL_LOG")" '1'

# Non-definitive outcomes degrade exactly as they do under by-name.
assert_eq "by-query transient 5xx -> error marker, not exists" \
  "$(run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t LUNAR_VAR_REF_LOOKUP=by-query" '' five http://fake:7007 | jq -c '.refs.system')" \
  '{"name":"five","error":"HTTP 502"}'
assert_eq "by-query connection error -> error marker" \
  "$(run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t LUNAR_VAR_REF_LOOKUP=by-query" boom '' http://fake:7007 | jq -c '.refs.domain')" \
  '{"name":"boom","error":"request failed (curl exit 7)"}'

# The one that matters most. by-query reports "no match" as an empty result
# set, so a 200 we cannot read must NOT collapse to that: recording
# `exists: false` here would fail the user's policy over OUR inability to
# parse the response — a gateway login page would read as a missing domain.
assert_eq "by-query 200 with a non-JSON body -> error, NOT exists:false" \
  "$(run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t LUNAR_VAR_REF_LOOKUP=by-query" login '' http://fake:7007 | jq -c '.refs.domain')" \
  '{"name":"login","error":"unparseable by-query response"}'
assert_eq "by-query 200 with no .items array -> error, NOT exists:false" \
  "$(run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t LUNAR_VAR_REF_LOOKUP=by-query" noitems '' http://fake:7007 | jq -c '.refs.domain')" \
  '{"name":"noitems","error":"unparseable by-query response"}'

# Query injection. Backstage ORs repeated `filter` params, so an unescaped `&`
# in a declared reference could append a second filter and turn a miss into a
# hit on an unrelated entity. The interpolated value must arrive encoded.
: > "$CURL_LOG"
run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t LUNAR_VAR_REF_LOOKUP=by-query" 'a&filter=kind=system' '' http://fake:7007 >/dev/null
assert_eq "by-query percent-encodes the interpolated ref value" \
  "$(grep -c 'metadata.name=a%26filter%3Dkind%3Dsystem' "$CURL_LOG")" '1'
assert_eq "by-query does not inject a second filter param" \
  "$(grep -c '&filter=kind=system' "$CURL_LOG" || true)" '0'

# by-query composes with the other two deployment-shape inputs: sigv4 signing
# and a gateway that strips the /api hop.
: > "$CURL_LOG"
assert_eq "by-query + sigv4 + root-mounted API resolves the ref" \
  "$(run_full "LUNAR_VAR_AUTH_MODE=sigv4 LUNAR_VAR_AWS_REGION=us-east-1 LUNAR_VAR_REF_LOOKUP=by-query LUNAR_VAR_API_PATH_PREFIX= $STATIC_KEYS" \
     payments '' http://fake:7007 | jq -c '.refs.domain')" \
  '{"name":"payments","exists":true}'
assert_eq "by-query + sigv4 signs the by-query URL at the root path" \
  "$(grep -c 'http://fake:7007/catalog/entities/by-query?limit=1&filter=kind=domain' "$CURL_LOG")" '1'
assert_eq "by-query + sigv4 passes the signing flags" \
  "$(grep -c -- '--aws-sigv4 aws:amz:us-east-1:execute-api' "$CURL_LOG")" '1'
assert_eq "by-query + sigv4 sends no Bearer header" \
  "$(grep -c 'Authorization: Bearer' "$CURL_LOG" || true)" '0'

# --- Degrade, don't fail --------------------------------------------------
# The whole point of the collector-vs-cataloger divergence: an auth problem
# must never cost us the parse/lint results. Each case asserts BOTH that the
# ref degraded to {name, error} AND that the lint output survived intact.
assert_degraded() {
  local desc="$1" out="$2" want_err="$3"
  assert_eq "$desc -> ref carries the error" \
    "$(echo "$out" | jq -c '.refs.domain')" \
    "{\"name\":\"payments\",\"error\":\"$want_err\"}"
  assert_eq "$desc -> .refs.checked still true" \
    "$(echo "$out" | jq -c '.refs.checked')" 'true'
  assert_eq "$desc -> parse/lint output preserved" \
    "$(echo "$out" | jq -c '{valid, kind, owner:.spec.owner}')" \
    '{"valid":true,"kind":"Component","owner":"team-demo"}'
}

assert_degraded "sigv4 without aws_region" \
  "$(run_full "LUNAR_VAR_AUTH_MODE=sigv4 $STATIC_KEYS" payments '' http://fake:7007)" \
  "aws_region required for sigv4"

assert_degraded "sigv4 with no resolvable credentials" \
  "$(run_full "LUNAR_VAR_AUTH_MODE=sigv4 LUNAR_VAR_AWS_REGION=us-east-1" payments '' http://fake:7007)" \
  "sigv4 credential resolution failed"

assert_degraded "invalid auth_mode" \
  "$(run_full "LUNAR_VAR_AUTH_MODE=oauth2" payments '' http://fake:7007)" \
  "invalid auth_mode 'oauth2' (expected 'bearer' or 'sigv4')"

assert_degraded "invalid ref_lookup" \
  "$(run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t LUNAR_VAR_REF_LOOKUP=by-id" payments '' http://fake:7007)" \
  "invalid ref_lookup 'by-id' (expected 'by-name' or 'by-query')"

# Both misconfigured: the auth message wins, since an unresolvable credential
# is the more fundamental fault and naming it first is the more useful hint.
assert_degraded "invalid auth_mode outranks invalid ref_lookup" \
  "$(run_full "LUNAR_VAR_AUTH_MODE=oauth2 LUNAR_VAR_REF_LOOKUP=by-id" payments '' http://fake:7007)" \
  "invalid auth_mode 'oauth2' (expected 'bearer' or 'sigv4')"

# A degraded run must not fire the request it knows cannot succeed.
: > "$CURL_LOG"
run_full "LUNAR_VAR_AUTH_MODE=sigv4 $STATIC_KEYS" payments '' http://fake:7007 >/dev/null
assert_eq "degraded run makes no Backstage request" \
  "$(grep -c 'fake:7007' "$CURL_LOG" || true)" '0'

: > "$CURL_LOG"
run_full "LUNAR_SECRET_BACKSTAGE_TOKEN=t LUNAR_VAR_REF_LOOKUP=by-id" payments '' http://fake:7007 >/dev/null
assert_eq "invalid ref_lookup makes no Backstage request" \
  "$(grep -c 'fake:7007' "$CURL_LOG" || true)" '0'

# aws_region falls back to the ambient AWS_REGION (IRSA sets it in-cluster).
: > "$CURL_LOG"
run_full "LUNAR_VAR_AUTH_MODE=sigv4 AWS_REGION=ap-south-1 $STATIC_KEYS" payments '' http://fake:7007 >/dev/null
assert_eq "aws_region falls back to the AWS_REGION env var" \
  "$(grep -c -- '--aws-sigv4 aws:amz:ap-south-1:execute-api' "$CURL_LOG")" '1'

# Auth mode is irrelevant when the feature is off — still no network at all.
: > "$CURL_LOG"
assert_eq "sigv4 with no backstage_url writes no .refs" \
  "$(run_full "LUNAR_VAR_AUTH_MODE=sigv4" payments payment-platform '' | jq -c '.refs')" \
  'null'
assert_eq "sigv4 with no backstage_url makes no requests at all" \
  "$(wc -l < "$CURL_LOG" | tr -d ' ')" '0'

# --- Transitive domain: component -> its system -> that system's domain ----
# A Component has no domain of its own in the Backstage model, so this is the
# only way to answer "is my domain real?" for an ordinary Component file.
echo
echo "Transitive system -> domain tests:"

for mode in by-name by-query; do
  MODE_ENV="LUNAR_SECRET_BACKSTAGE_TOKEN=test-token LUNAR_VAR_REF_LOOKUP=$mode"

  # The customer case: the system resolves, but the domain IT belongs to does
  # not. `system-exists` is happy; only the transitive entry catches this.
  DANGLING=$(run_full "$MODE_ENV" '' dangling-system http://fake:7007 | jq -c '.refs')
  assert_eq "[$mode] system resolves but its domain is missing -> exists:false" \
    "$(echo "$DANGLING" | jq -c '.system_domain')" \
    '{"name":"typo-domain","exists":false,"via_system":"dangling-system"}'
  assert_eq "[$mode] a dangling system domain leaves system-exists passing" \
    "$(echo "$DANGLING" | jq -c '.system.exists')" 'true'
  assert_eq "[$mode] the component declares no spec.domain, so .refs.domain stays absent" \
    "$(echo "$DANGLING" | jq -c 'has("domain")')" 'false'

  # Healthy chain.
  assert_eq "[$mode] healthy chain -> exists:true" \
    "$(run_full "$MODE_ENV" '' payment-platform http://fake:7007 | jq -c '.refs.system_domain')" \
    '{"name":"payments","exists":true,"via_system":"payment-platform"}'

  # A System that belongs to no domain is legitimate: no entry, no false fail.
  assert_eq "[$mode] system belonging to no domain writes no system_domain" \
    "$(run_full "$MODE_ENV" '' team-nodomain http://fake:7007 | jq -c 'has("system_domain")')" \
    'false'

  # An unresolvable system has no entity to read a domain off, and the failure
  # is already `system-exists`'s to report — don't double-report it.
  assert_eq "[$mode] missing system writes no system_domain" \
    "$(run_full "$MODE_ENV" '' typo-system http://fake:7007 | jq -c '.refs | has("system_domain")')" \
    'false'

  # A transient failure resolving the system stops the hop too.
  assert_eq "[$mode] errored system lookup writes no system_domain" \
    "$(run_full "$MODE_ENV" '' five http://fake:7007 | jq -c '.refs | has("system_domain")')" \
    'false'

  # A bare spec.domain on the System resolves against the SYSTEM's namespace,
  # not the component's — they can differ.
  : > "$CURL_LOG"
  run_full "$MODE_ENV" '' other-ns/remote-system http://fake:7007 comp-ns >/dev/null
  assert_eq "[$mode] the domain hop uses the system's namespace, not the component's" \
    "$(grep -c 'other-ns' "$CURL_LOG")" '2'
  assert_eq "[$mode] and never looks the domain up in the component's namespace" \
    "$(grep -c 'domain/comp-ns/' "$CURL_LOG" || true)" '0'
done

# The transitive entry is additive: a `kind: System` catalog file still gets its
# own `.refs.domain` from spec.domain, unchanged by any of the above.
assert_eq "kind:System file still reports its own dangling spec.domain" \
  "$(run_collect_url http://fake:7007 <<'EOF' | jq -c '.refs'
apiVersion: backstage.io/v1alpha1
kind: System
metadata: {name: orphan-system}
spec: {owner: team-demo, domain: typo-domain}
EOF
)" \
  '{"checked":true,"domain":{"name":"typo-domain","exists":false}}'

if [ "$FAILS" -eq 0 ]; then
  echo "All referential-integrity and auth-mode tests passed."
else
  echo "$FAILS test(s) failed."
  exit 1
fi
