#!/bin/bash
#
# Offline test for the pagerduty collector's service-ID resolution. Stubs
# `curl` and `lunar` on PATH and runs oncall.sh from a per-case checkout dir,
# so no network, no AWS, no Backstage and no Lunar Hub are needed.
#
# The mock curl logs every invocation (so cases can assert which endpoints and
# auth flags were used) and answers:
#   * AWS metadata endpoints -> unreachable, so the credential chain is
#     deterministic whatever the host exposes.
#   * STS AssumeRoleWithWebIdentity -> credentials when MOCK_STS=1. STS
#     AssumeRole, keyed off the role: *denied* -> AccessDenied, *unreachable*
#     -> curl exit 28, else credentials for the assumed role.
#   * Backstage by-name / by-query from test/fixtures/backstage-entities.yaml,
#     except these names: boom -> connection error, five -> HTTP 502,
#     login -> a 200 HTML login page, noitems -> a 200 without `.items`.
#   * PagerDuty /services, /escalation_policies, /schedules. PGONE00 -> 404.
#
# Run: ./test-local.sh   (needs bash, jq, yq, python3)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT
MOCK="$TEST_DIR/bin"
mkdir -p "$MOCK"

CURL_LOG="$TEST_DIR/curl.log"
ENTITIES="$TEST_DIR/entities.json"
yq ea -o=json '[.]' "$SCRIPT_DIR/test/fixtures/backstage-entities.yaml" > "$ENTITIES"

# --- Mock curl ------------------------------------------------------------
cat > "$MOCK/curl" << 'EOF'
#!/bin/bash
printf '%s\n' "$*" >> "$CURL_LOG"

args="$*"
case "$args" in
  *169.254.169.254*|*169.254.170.2*) exit 7 ;;
  *sts.*amazonaws.com*AssumeRoleWithWebIdentity*)
    if [ "${MOCK_STS:-0}" = "1" ]; then
      printf '%s' '<AssumeRoleWithWebIdentityResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/"><AssumeRoleWithWebIdentityResult><Credentials><AccessKeyId>ASIAMOCKKEY</AccessKeyId><SecretAccessKey>mocksecret</SecretAccessKey><SessionToken>mocksessiontoken</SessionToken></Credentials></AssumeRoleWithWebIdentityResult></AssumeRoleWithWebIdentityResponse>'
      exit 0
    fi
    exit 7 ;;
  *sts.*amazonaws.com*Action=AssumeRole*)
    case "$args" in
      *RoleArn=*denied*)
        printf '%s' '<ErrorResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/"><Error><Type>Sender</Type><Code>AccessDenied</Code><Message>not authorized</Message></Error></ErrorResponse>'
        exit 0 ;;
      *RoleArn=*unreachable*) exit 28 ;;
      *)
        printf '%s' '<AssumeRoleResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/"><AssumeRoleResult><Credentials><AccessKeyId>ASIAASSUMED</AccessKeyId><SecretAccessKey>assumedsecret</SecretAccessKey><SessionToken>assumedtoken</SessionToken></Credentials></AssumeRoleResult></AssumeRoleResponse>'
        exit 0 ;;
    esac ;;
  *sts.*amazonaws.com*) exit 7 ;;
esac

out=""
prev=""
for a in "$@"; do
  [ "$prev" = "-o" ] && out="$a"
  prev="$a"
done
url="${*: -1}"

# PagerDuty. pd_get passes `-o <file> -w '%{http_code}'`: body to the file,
# status code on stdout.
pd() {
  printf '%s' "$2" > "$out"
  printf '%s' "$1"
  exit 0
}
case "$url" in
  */services/*)
    sid="${url##*/services/}"
    printf '%s' "$sid" > "$MOCK_DIR/requested_service"
    [ "$sid" = "PGONE00" ] && pd 404 '{"error":{"message":"Not Found","code":2100}}'
    pd 200 "{\"service\":{\"id\":\"$sid\",\"name\":\"Service $sid\",\"status\":\"active\",\"escalation_policy\":{\"id\":\"PEP0001\"}}}" ;;
  */escalation_policies/PEP0001)
    pd 200 '{"escalation_policy":{"name":"Primary","escalation_rules":[{"targets":[{"type":"schedule_reference","id":"PSCH001"}]},{"targets":[{"type":"user_reference","id":"PUSER01"}]}]}}' ;;
  */schedules/PSCH001)
    pd 200 '{"schedule":{"schedule_layers":[{"rotation_turn_length_seconds":604800,"users":[{"user":{"id":"PUSER01"}},{"user":{"id":"PUSER02"}}]}]}}' ;;
esac

# Backstage, answered in the `<body>\n<http_code>` shape `-w '\n%{http_code}'`
# produces. Like the real catalog, responses always carry metadata.namespace.
lookup() {
  jq -c --arg k "$1" --arg ns "$2" --arg n "$3" '
    map(.metadata.namespace //= "default")
    | map(select((.kind | ascii_downcase) == $k and .metadata.namespace == $ns and .metadata.name == $n))
    | .[0] // empty' "$ENTITIES"
}
special() {
  case "$1" in
    boom) exit 7 ;;
    five) printf '%s\n502' '{"message":"bad gateway"}'; exit 0 ;;
    login) printf '%s\n200' '<html><body>SSO login</body></html>'; exit 0 ;;
    noitems) printf '%s\n200' '{"totalItems":0}'; exit 0 ;;
  esac
}
case "$url" in
  */catalog/entities/by-query\?*)
    filter="${url##*filter=}"
    filter="${filter%%&*}"
    filter=$(printf '%b' "${filter//%/\\x}")
    kind="${filter#kind=}"
    kind="${kind%%,*}"
    ns="${filter##*metadata.namespace=}"
    ns="${ns%%,*}"
    name="${filter##*metadata.name=}"
    special "$name"
    e=$(lookup "$kind" "$ns" "$name")
    if [ -n "$e" ]; then
      printf '{"items":[%s],"totalItems":1,"pageInfo":{}}\n200' "$e"
    else
      printf '%s\n200' '{"items":[],"totalItems":0,"pageInfo":{}}'
    fi
    exit 0 ;;
  */catalog/entities/by-name/*)
    rest="${url##*/by-name/}"
    kind="${rest%%/*}"
    rest="${rest#*/}"
    ns="${rest%%/*}"
    name="${rest#*/}"
    special "$name"
    e=$(lookup "$kind" "$ns" "$name")
    if [ -n "$e" ]; then
      printf '%s\n200' "$e"
    else
      printf '%s\n404' '{"error":{"name":"NotFoundError"}}'
    fi
    exit 0 ;;
esac

echo "mock curl: unhandled URL: $url" >&2
exit 7
EOF
chmod +x "$MOCK/curl"

# --- Mock lunar: append each `lunar collect -j <path> -` write to a file ----
cat > "$MOCK/lunar" << 'EOF'
#!/bin/bash
if [ "${1:-}" = "collect" ] && [ "${2:-}" = "-j" ]; then
  safe="${3//[^a-zA-Z0-9]/_}"
  cat >> "$MOCK_DIR/collect${safe}.out"
fi
exit 0
EOF
chmod +x "$MOCK/lunar"

# catalog <name> [namespace] [annotation-line] — a one-Component
# catalog-info.yaml naming the entity to look up.
catalog() {
  echo "apiVersion: backstage.io/v1alpha1"
  echo "kind: Component"
  echo "metadata:"
  echo "  name: $1"
  if [ -n "${2:-}" ]; then echo "  namespace: $2"; fi
  if [ -n "${3:-}" ]; then
    echo "  annotations:"
    echo "    $3"
  fi
  echo "spec:"
  echo "  type: service"
  echo "  owner: team-test"
}

# run_case <name> [KEY=VALUE ...] — runs oncall.sh in $TEST_DIR/cases/<name>
# with a clean environment plus the given variables. The case dir is the
# checkout: write its catalog-info.yaml to "$CASE/catalog-info.yaml" first via
# `new_case`. The PagerDuty key is set unless a case clears it.
new_case() {
  CASE="$TEST_DIR/cases/$1"
  rm -rf "$CASE"
  mkdir -p "$CASE"
}
run_case() {
  : > "$CURL_LOG"
  ( cd "$CASE" && env -i PATH="$MOCK:$PATH" MOCK_DIR="$CASE" CURL_LOG="$CURL_LOG" ENTITIES="$ENTITIES" \
      LUNAR_SECRET_PAGERDUTY_API_KEY=pd-test-key LUNAR_VAR_PAGERDUTY_BASE_URL=https://pd.test \
      "$@" bash "$SCRIPT_DIR/oncall.sh" ) > "$CASE/stdout" 2> "$CASE/stderr" \
    || echo "oncall.sh exited $?" >> "$CASE/stderr"
}

# got <path-suffix> — what was collected at .oncall.<suffix>, or null.
got() {
  local f="$CASE/collect_oncall_$1.out"
  if [ -s "$f" ]; then jq -sc 'add' "$f"; else echo null; fi
}
queried() { cat "$CASE/requested_service" 2>/dev/null || echo none; }
via() { got service | jq -r '.discovered_via // "none"'; }
count() { grep -c -- "$1" "$CURL_LOG" || true; }
writes() {
  local n=0 f
  for f in "$CASE"/collect*.out; do
    [ -e "$f" ] && n=$((n + 1))
  done
  echo "$n"
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
    echo "    stderr: $(tr '\n' '|' < "$CASE/stderr" | head -c 600)"
    FAILS=$((FAILS + 1))
  fi
}

BS="LUNAR_VAR_BACKSTAGE_DISCOVERY=true"
LIVE=(LUNAR_VAR_BACKSTAGE_DISCOVERY=true LUNAR_VAR_BACKSTAGE_URL=http://bs.test:7007 LUNAR_SECRET_BACKSTAGE_TOKEN=bs-token)
STATIC_KEYS=(LUNAR_SECRET_AWS_ACCESS_KEY_ID=AKIATEST LUNAR_SECRET_AWS_SECRET_ACCESS_KEY=secret123)
SIGV4=("${LIVE[@]}" LUNAR_VAR_BACKSTAGE_AUTH_MODE=sigv4 LUNAR_VAR_AWS_REGION=us-east-1)

echo "Resolution from meta, input and the checked-out file:"

new_case dotcom
cp "$SCRIPT_DIR/test/fixtures/catalog-info-dotcom.yaml" "$CASE/catalog-info.yaml"
run_case "$BS"
assert_eq "file: pagerduty.com/service-id drives the query" "$(queried) $(via)" "PABC123 file:catalog-info.yaml"
assert_eq "file: the full service record is written" \
  "$(got service | jq -c '{id, name, status}')" '{"id":"PABC123","name":"Service PABC123","status":"active"}'
assert_eq "file: schedule and escalation still collected" \
  "$(got schedule | jq -c .) $(got escalation | jq -c '.levels')" '{"exists":true,"participants":2,"rotation":"weekly"} 2'
assert_eq "file: no .oncall.unmapped on a mapped component" "$(got unmapped)" "null"

new_case lunarkey
cp "$SCRIPT_DIR/test/fixtures/catalog-info-lunarkey.yaml" "$CASE/catalog-info.yaml"
run_case "$BS"
assert_eq "file: second key, skipping a non-Component document" "$(queried) $(via)" "PDEF456 file:catalog-info.yaml"

new_case meta
catalog payment-api > "$CASE/catalog-info.yaml"
run_case "${LIVE[@]}" 'LUNAR_COMPONENT_META={"pagerduty/service-id":"PMETA01"}' LUNAR_VAR_SERVICE_ID=PINPUT9
assert_eq "meta wins over the input and discovery" "$(queried) $(via)" "PMETA01 meta:pagerduty/service-id"
assert_eq "meta: no Backstage request" "$(count bs.test)" "0"

new_case input
catalog payment-api > "$CASE/catalog-info.yaml"
run_case "${LIVE[@]}" LUNAR_VAR_SERVICE_ID=PINPUT9
assert_eq "input wins over discovery" "$(queried) $(via)" "PINPUT9 input:service_id"
assert_eq "input: no Backstage request" "$(count bs.test)" "0"

new_case discovery-off
catalog payment-api "" "pagerduty.com/service-id: PABC123" > "$CASE/catalog-info.yaml"
run_case LUNAR_VAR_BACKSTAGE_URL=http://bs.test:7007
assert_eq "discovery off: no query" "$(queried)" "none"
assert_eq "discovery off: unmapped, listing meta and input" \
  "$(got unmapped)" '{"searched":["meta:pagerduty/service-id","input:service_id"]}'
assert_eq "discovery off: backstage_url alone makes no request" "$(count bs.test)" "0"
assert_eq "unmapped: .oncall.source names the tool" "$(got source)" '{"tool":"pagerduty","integration":"api"}'
assert_eq "unmapped: no .oncall.service" "$(got service)" "null"

new_case no-file
run_case "$BS"
assert_eq "no catalog file: unmapped, both candidate paths listed" \
  "$(got unmapped | jq -c '.searched[2:]')" '["file:catalog-info.yaml (not found)","file:catalog-info.yml (not found)"]'

new_case bad-yaml
printf 'kind: [unclosed\n' > "$CASE/catalog-info.yaml"
run_case "${LIVE[@]}"
assert_eq "unparseable catalog file: unmapped, no Backstage request" \
  "$(got unmapped | jq -c '.searched[2:]') $(count bs.test)" '["file:catalog-info.yaml (unparseable)"] 0'

new_case no-secret
catalog payment-api > "$CASE/catalog-info.yaml"
run_case "${LIVE[@]}" LUNAR_SECRET_PAGERDUTY_API_KEY=
assert_eq "no PAGERDUTY_API_KEY: nothing written, no requests" \
  "$(writes) $(wc -l < "$CURL_LOG" | tr -d ' ')" "0 0"

new_case invalid-id
catalog payment-api "" "pagerduty.com/service-id: '../users?limit=100'" > "$CASE/catalog-info.yaml"
run_case "$BS"
assert_eq "a value that isn't a PagerDuty ID is never sent" "$(queried) $(count pd.test)" "none 0"
assert_eq "but is recorded with where it came from" \
  "$(got service)" '{"id":"../users?limit=100","discovered_via":"file:catalog-info.yaml"}'

new_case pd-404
catalog payment-api "" "pagerduty.com/service-id: PGONE00" > "$CASE/catalog-info.yaml"
run_case "$BS"
assert_eq "PagerDuty 404: the mapping is still recorded, with its source" \
  "$(got service)" '{"id":"PGONE00","discovered_via":"file:catalog-info.yaml"}'
assert_eq "PagerDuty 404: not reported as unmapped" "$(got unmapped)" "null"

echo "Live Backstage lookup:"

for mode in by-name by-query; do
  M=("${LIVE[@]}" "LUNAR_VAR_BACKSTAGE_REF_LOOKUP=$mode")

  new_case "$mode-component"
  catalog payment-api > "$CASE/catalog-info.yaml"
  run_case "${M[@]}"
  assert_eq "[$mode] the Component's own annotation" "$(queried) $(via)" "PCOMP01 component:default/payment-api"
  assert_eq "[$mode] one request when the Component answers" "$(count bs.test)" "1"
  assert_eq "[$mode] bearer token sent" "$(count 'Authorization: Bearer bs-token')" "1"

  new_case "$mode-system"
  catalog checkout > "$CASE/catalog-info.yaml"
  run_case "${M[@]}"
  assert_eq "[$mode] inherited from the System" "$(queried) $(via)" "PSYS001 system:default/payment-platform"

  new_case "$mode-domain"
  catalog ledger-api > "$CASE/catalog-info.yaml"
  run_case "${M[@]}"
  assert_eq "[$mode] inherited from the System's Domain" "$(queried) $(via)" "PDOM001 domain:default/finance"
  assert_eq "[$mode] three requests: component, system, domain" "$(count bs.test)" "3"

  new_case "$mode-namespaces"
  catalog alpha ops > "$CASE/catalog-info.yaml"
  run_case "${M[@]}"
  assert_eq "[$mode] qualified system ref, bare domain resolved in the System's namespace" \
    "$(queried) $(via)" "PDOMNS1 domain:platform/infra"

  new_case "$mode-live-beats-file"
  catalog checkout "" "pagerduty.com/service-id: PFILE01" > "$CASE/catalog-info.yaml"
  run_case "${M[@]}"
  assert_eq "[$mode] the live entity wins over the checked-out file" "$(queried) $(via)" "PSYS001 system:default/payment-platform"

  new_case "$mode-miss-file"
  catalog orphan "" "pagerduty.com/service-id: PFILE01" > "$CASE/catalog-info.yaml"
  run_case "${M[@]}"
  assert_eq "[$mode] a live miss falls back to the file" "$(queried) $(via)" "PFILE01 file:catalog-info.yaml"

  new_case "$mode-miss"
  catalog orphan > "$CASE/catalog-info.yaml"
  run_case "${M[@]}"
  assert_eq "[$mode] no annotation anywhere: unmapped, every lookup listed" \
    "$(got unmapped)" '{"searched":["meta:pagerduty/service-id","input:service_id","component:default/orphan","file:catalog-info.yaml"]}'
  assert_eq "[$mode] unmapped: no PagerDuty query" "$(queried)" "none"

  new_case "$mode-quiet"
  catalog quiet > "$CASE/catalog-info.yaml"
  run_case "${M[@]}"
  assert_eq "[$mode] System with no annotation and no domain: unmapped" \
    "$(got unmapped | jq -c '.searched[2:4]')" '["component:default/quiet","system:default/standalone-system"]'

  new_case "$mode-dangling"
  catalog lonely > "$CASE/catalog-info.yaml"
  run_case "${M[@]}"
  assert_eq "[$mode] a System missing from the catalog is marked" \
    "$(got unmapped | jq -c '.searched[3]')" '"system:default/ghost-system (not in catalog)"'

  new_case "$mode-unregistered"
  catalog not-registered > "$CASE/catalog-info.yaml"
  run_case "${M[@]}"
  assert_eq "[$mode] a Component missing from the catalog is marked" \
    "$(got unmapped | jq -c '.searched[2]')" '"component:default/not-registered (not in catalog)"'

  for broken in five boom login; do
    new_case "$mode-$broken"
    catalog "$broken" > "$CASE/catalog-info.yaml"
    run_case "${M[@]}"
    assert_eq "[$mode] lookup that can't complete ($broken): nothing written" \
      "$(writes)" "0"
    assert_eq "[$mode] and the failure is logged" \
      "$(grep -c 'live Backstage lookup failed' "$CASE/stderr" || true)" "1"
  done

  new_case "$mode-error-file"
  catalog five "" "pagerduty/service-id: PFILE02" > "$CASE/catalog-info.yaml"
  run_case "${M[@]}"
  assert_eq "[$mode] a failed lookup still falls back to the file" "$(queried) $(via)" "PFILE02 file:catalog-info.yaml"
done

new_case by-name-url
catalog checkout > "$CASE/catalog-info.yaml"
run_case "${LIVE[@]}"
assert_eq "by-name is the default endpoint" \
  "$(count 'http://bs.test:7007/api/catalog/entities/by-name/component/default/checkout') $(count by-query)" "1 0"
assert_eq "by-name follows to the system" \
  "$(count 'http://bs.test:7007/api/catalog/entities/by-name/system/default/payment-platform')" "1"

new_case by-query-url
catalog checkout > "$CASE/catalog-info.yaml"
run_case "${LIVE[@]}" LUNAR_VAR_BACKSTAGE_REF_LOOKUP=by-query
assert_eq "by-query sends the encoded entity filter, never by-name" \
  "$(count 'by-query?limit=1&filter=kind%3Dcomponent%2Cmetadata.namespace%3Ddefault%2Cmetadata.name%3Dcheckout') $(count by-name)" "1 0"

new_case by-query-noitems
catalog noitems > "$CASE/catalog-info.yaml"
run_case "${LIVE[@]}" LUNAR_VAR_BACKSTAGE_REF_LOOKUP=by-query
assert_eq "by-query 200 without .items: a failed lookup, not a miss" "$(got unmapped) $(got source)" "null null"

new_case prefix-root
catalog checkout > "$CASE/catalog-info.yaml"
run_case "${LIVE[@]}" LUNAR_VAR_BACKSTAGE_API_PATH_PREFIX= LUNAR_VAR_BACKSTAGE_URL=http://bs.test:7007/
assert_eq "empty backstage_api_path_prefix mounts the API at the root" \
  "$(count 'http://bs.test:7007/catalog/entities/by-name/component/default/checkout') $(count /api/)" "1 0"

new_case custom-key
catalog checkout > "$CASE/catalog-info.yaml"
run_case "${LIVE[@]}" LUNAR_VAR_BACKSTAGE_ANNOTATIONS=pagerduty/service-id
assert_eq "backstage_annotations narrows the keys read off live entities" "$(via)" "system:default/payment-platform"
run_case "${LIVE[@]}" LUNAR_VAR_BACKSTAGE_ANNOTATIONS=acme.com/pd
assert_eq "an annotation key no entity carries: unmapped" "$(got unmapped | jq -c '.searched | length')" "6"

new_case no-component
printf 'apiVersion: backstage.io/v1alpha1\nkind: System\nmetadata: {name: payment-platform}\nspec: {owner: t}\n' > "$CASE/catalog-info.yaml"
run_case "${LIVE[@]}"
assert_eq "a file with no Component: no lookup, unmapped" "$(count bs.test) $(got unmapped | jq -c '.searched[2]')" '0 "file:catalog-info.yaml"'

echo "Backstage auth (bearer / sigv4):"

new_case sigv4-static
catalog checkout > "$CASE/catalog-info.yaml"
run_case "${SIGV4[@]}" "${STATIC_KEYS[@]}"
assert_eq "sigv4: resolves like bearer" "$(via)" "system:default/payment-platform"
assert_eq "sigv4: both lookups signed for execute-api" "$(count '--aws-sigv4 aws:amz:us-east-1:execute-api --user AKIATEST:secret123')" "2"
assert_eq "sigv4: no Bearer header" "$(count 'Authorization: Bearer')" "0"

new_case sigv4-service
catalog payment-api > "$CASE/catalog-info.yaml"
run_case "${SIGV4[@]}" "${STATIC_KEYS[@]}" LUNAR_VAR_AWS_SERVICE=lambda LUNAR_SECRET_AWS_SESSION_TOKEN=tmptok
assert_eq "sigv4: aws_service and the session token reach the request" \
  "$(count 'aws:amz:us-east-1:lambda') $(count 'x-amz-security-token: tmptok')" "1 1"

new_case sigv4-irsa
catalog payment-api > "$CASE/catalog-info.yaml"
echo "mock-web-identity-token" > "$TEST_DIR/wit"
run_case "${SIGV4[@]}" "${STATIC_KEYS[@]}" MOCK_STS=1 AWS_ROLE_ARN=arn:aws:iam::123456789012:role/r AWS_WEB_IDENTITY_TOKEN_FILE="$TEST_DIR/wit"
assert_eq "sigv4: IRSA credentials win over static keys" \
  "$(count '--user ASIAMOCKKEY:mocksecret -H x-amz-security-token: mocksessiontoken http://bs.test')" "1"
assert_eq "sigv4: IRSA session named for this collector" "$(count 'RoleSessionName=lunar-pagerduty-collector')" "1"

OK_ROLE="arn:aws:iam::210987654321:role/backstage-api-reader"
new_case sigv4-assume
catalog checkout > "$CASE/catalog-info.yaml"
run_case "${SIGV4[@]}" "${STATIC_KEYS[@]}" LUNAR_VAR_AWS_ASSUME_ROLE_ARNS="arn:aws:iam::210987654321:role/denied, $OK_ROLE"
assert_eq "assume role: tried in order, named for this collector" \
  "$(count 'Action=AssumeRole ') $(count "RoleArn=$OK_ROLE --data-urlencode RoleSessionName=lunar-pagerduty-collector")" "2 1"
assert_eq "assume role: lookups signed with the assumed role" \
  "$(count '--user ASIAASSUMED:assumedsecret -H x-amz-security-token: assumedtoken http://bs.test')" "2"
assert_eq "assume role: resolves through the walk" "$(via)" "system:default/payment-platform"

for setup in "no-region|LUNAR_VAR_AWS_REGION=|aws_region required for sigv4" \
             "no-creds|LUNAR_SECRET_AWS_ACCESS_KEY_ID=|sigv4 credential resolution failed" \
             "denied|LUNAR_VAR_AWS_ASSUME_ROLE_ARNS=arn:aws:iam::1:role/denied|sts:AssumeRole failed" \
             "bad-mode|LUNAR_VAR_BACKSTAGE_AUTH_MODE=oauth2|invalid backstage_auth_mode 'oauth2'" \
             "bad-lookup|LUNAR_VAR_BACKSTAGE_REF_LOOKUP=by-id|invalid backstage_ref_lookup 'by-id'"; do
  IFS='|' read -r label override message <<< "$setup"
  new_case "setup-$label"
  catalog checkout > "$CASE/catalog-info.yaml"
  run_case "${SIGV4[@]}" "${STATIC_KEYS[@]}" "$override"
  assert_eq "setup error ($label): no Backstage request, nothing written" \
    "$(count bs.test) $(writes)" "0 0"
  assert_eq "setup error ($label): logged" "$(grep -c "live lookup not run: $message" "$CASE/stderr" || true)" "1"
  catalog checkout "" "pagerduty.com/service-id: PFILE03" > "$CASE/catalog-info.yaml"
  run_case "${SIGV4[@]}" "${STATIC_KEYS[@]}" "$override"
  assert_eq "setup error ($label): the file still answers" "$(queried) $(via)" "PFILE03 file:catalog-info.yaml"
done

echo
if [ "$FAILS" -eq 0 ]; then
  echo "All pagerduty collector tests passed."
else
  echo "$FAILS test(s) failed."
  exit 1
fi
