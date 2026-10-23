#!/bin/bash
#
# Offline test for the pagerduty collector's service-ID resolution. Stubs
# `curl`, `lunar` and `sleep` on PATH and runs the scripts from a per-case
# checkout dir, so no network, no Backstage and no Lunar Hub are needed.
#
# The live-catalog cases first run the real backstage collector
# ($BACKSTAGE_DIR/main.sh) against the mock Backstage, then serve what it
# collected to from-backstage-collector.sh / oncall.sh as the Component JSON. So the two
# collectors' contract is tested end to end, not against a hand-written blob.
#
# The mock curl answers:
#   * Backstage by-name / by-query from test/fixtures/backstage-entities.yaml,
#     except these names: boom -> connection error, five -> HTTP 502,
#     login -> a 200 HTML login page, notentity -> a 200 JSON body that isn't
#     an entity.
#   * PagerDuty /services, /escalation_policies, /schedules. PGONE00 -> 404.
# The mock `lunar component get-json` serves $CASE/component.json; the first
# MOCK_GETJSON_FAIL calls fail and the next MOCK_GETJSON_STALE calls return a
# blob without the backstage lookup, for the retry cases.
#
# Run: ./test-local.sh   (needs bash, jq, yq, python3)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKSTAGE_DIR="${BACKSTAGE_DIR:-$SCRIPT_DIR/../backstage}"
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
    notentity) printf '%s\n200' '{"message":"sign in required"}'; exit 0 ;;
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

# --- Mock lunar ----------------------------------------------------------
# `collect -j <path> -` appends the write to a per-path file. `component
# get-json` logs its arguments and serves $MOCK_DIR/component.json.
cat > "$MOCK/lunar" << 'EOF'
#!/bin/bash
if [ "${1:-}" = "collect" ] && [ "${2:-}" = "-j" ]; then
  safe="${3//[^a-zA-Z0-9]/_}"
  cat >> "$MOCK_DIR/collect${safe}.out"
  exit 0
fi
if [ "${1:-}" = "component" ] && [ "${2:-}" = "get-json" ]; then
  printf '%s\n' "${*:3}" >> "$MOCK_DIR/getjson.log"
  n=$(wc -l < "$MOCK_DIR/getjson.log")
  if [ "$n" -le "${MOCK_GETJSON_FAIL:-0}" ]; then
    echo "Error: rpc error: code = NotFound desc = component not found" >&2
    printf 'Usage:\n  lunar component get-json [flags]\n' >&2
    exit 1
  fi
  if [ "$n" -le $(( ${MOCK_GETJSON_FAIL:-0} + ${MOCK_GETJSON_STALE:-0} )) ]; then
    echo '{"catalog":{"native":{"backstage":{"valid":true,"kind":"Component"}}}}'
    exit 0
  fi
  cat "$MOCK_DIR/component.json"
  exit 0
fi
exit 0
EOF
chmod +x "$MOCK/lunar"

# --- Mock sleep: record the backoff instead of waiting --------------------
cat > "$MOCK/sleep" << 'EOF'
#!/bin/bash
printf '%s\n' "$1" >> "$MOCK_DIR/sleeps"
EOF
chmod +x "$MOCK/sleep"

# catalog <name> [namespace] [annotation-line] [system] — a one-Component
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
  echo "  lifecycle: production"
  echo "  owner: team-test"
  if [ -n "${4:-}" ]; then echo "  system: $4"; fi
}

# new_case <name> — a fresh checkout dir; write its catalog-info.yaml to
# "$CASE/catalog-info.yaml" before backstage_json / run_case. Set CASE_CWD to
# run the collectors from a subdirectory (a monorepo component).
new_case() {
  CASE="$TEST_DIR/cases/$1"
  CASE_CWD=""
  rm -rf "$CASE"
  mkdir -p "$CASE/bs"
}

# backstage_json [KEY=VALUE ...] — runs the real backstage collector on the
# case's catalog-info.yaml against the mock Backstage and stores what it
# collected as the case's Component JSON.
backstage_json() {
  : > "$CURL_LOG"
  ( cd "${CASE_CWD:-$CASE}" && env -i PATH="$MOCK:$PATH" MOCK_DIR="$CASE/bs" CURL_LOG="$CURL_LOG" ENTITIES="$ENTITIES" \
      LUNAR_VAR_PATHS="catalog-info.yaml,catalog-info.yml" \
      LUNAR_VAR_BACKSTAGE_URL=http://bs.test:7007 LUNAR_SECRET_BACKSTAGE_TOKEN=bs-token \
      "$@" bash "$BACKSTAGE_DIR/main.sh" ) > /dev/null 2> "$CASE/bs/stderr"
  jq '{catalog: {native: {backstage: .}}}' "$CASE/bs/collect_catalog_native_backstage.out" > "$CASE/component.json"
}

# run_case <script> [KEY=VALUE ...] — runs oncall.sh or from-backstage-collector.sh in the
# case dir with a clean environment plus the given variables. The PagerDuty key
# is set unless a case clears it.
run_case() {
  local script="$1"
  shift
  : > "$CURL_LOG"
  CASE_EXIT=0
  ( cd "${CASE_CWD:-$CASE}" && env -i PATH="$MOCK:$PATH" MOCK_DIR="$CASE" CURL_LOG="$CURL_LOG" ENTITIES="$ENTITIES" \
      TMPDIR="$CASE" LUNAR_COMPONENT_ID=github.com/acme/svc LUNAR_COMPONENT_GIT_SHA=abc123 \
      LUNAR_SECRET_PAGERDUTY_API_KEY=pd-test-key LUNAR_VAR_PAGERDUTY_BASE_URL=https://pd.test \
      "$@" bash "$SCRIPT_DIR/$script" ) > "$CASE/stdout" 2> "$CASE/stderr" || CASE_EXIT=$?
}

# got <path-suffix> — what was collected at .oncall.<suffix>, or null.
got() {
  local f="$CASE/collect_oncall_$1.out"
  if [ -s "$f" ]; then jq -sc 'add' "$f"; else echo null; fi
}
# svc_lookup — .oncall.service_lookup merged the way Lunar merges two writers:
# arrays concatenate. null when nothing was written there.
svc_lookup() {
  local f="$CASE/collect_oncall_service_lookup.out"
  if [ -s "$f" ]; then
    jq -sc '{searched: (map(.searched // []) | add), errors: (map(.errors // []) | add)}
            | with_entries(select(.value | length > 0))' "$f"
  else
    echo null
  fi
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
reads() { if [ -f "$CASE/getjson.log" ]; then wc -l < "$CASE/getjson.log" | tr -d ' '; else echo 0; fi; }
logged() { grep -c -- "$1" "$CASE/stderr" || true; }
slept() { awk '{ s += $1 } END { print s + 0 }' "$CASE/sleeps" 2>/dev/null || echo 0; }
longest_sleep() { awk '$1 > m { m = $1 } END { print m + 0 }' "$CASE/sleeps" 2>/dev/null || echo 0; }

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

FILE=LUNAR_VAR_BACKSTAGE_DISCOVERY=true
CRON=LUNAR_COLLECTOR_NAME=pagerduty.oncall-cron

echo "oncall: meta, input and the checked-out file:"

new_case dotcom
cp "$SCRIPT_DIR/test/fixtures/catalog-info-dotcom.yaml" "$CASE/catalog-info.yaml"
run_case oncall.sh "$FILE"
assert_eq "file: pagerduty.com/service-id drives the query" "$(queried) $(via)" "PABC123 file:catalog-info.yaml"
assert_eq "file: the full service record is written" \
  "$(got service | jq -c '{id, name, status}')" '{"id":"PABC123","name":"Service PABC123","status":"active"}'
assert_eq "file: schedule and escalation still collected" \
  "$(got schedule | jq -c .) $(got escalation | jq -c '.levels')" '{"exists":true,"participants":2,"rotation":"weekly"} 2'
assert_eq "file: no .oncall.service_lookup on a mapped component" "$(svc_lookup)" "null"
assert_eq "file: no Component JSON read" "$(reads)" "0"

new_case lunarkey
cp "$SCRIPT_DIR/test/fixtures/catalog-info-lunarkey.yaml" "$CASE/catalog-info.yaml"
run_case oncall.sh "$FILE"
assert_eq "file: second key, skipping a non-Component document" "$(queried) $(via)" "PDEF456 file:catalog-info.yaml"

new_case meta
catalog payment-api > "$CASE/catalog-info.yaml"
run_case oncall.sh "$FILE" 'LUNAR_COMPONENT_META={"pagerduty/service-id":"PMETA01"}' LUNAR_VAR_SERVICE_ID=PINPUT9
assert_eq "meta wins over the input and the file" "$(queried) $(via)" "PMETA01 meta:pagerduty/service-id"

new_case input
catalog payment-api "" "pagerduty.com/service-id: PABC123" > "$CASE/catalog-info.yaml"
run_case oncall.sh "$FILE" LUNAR_VAR_SERVICE_ID=PINPUT9
assert_eq "input wins over the file" "$(queried) $(via)" "PINPUT9 input:service_id"

new_case discovery-off
catalog payment-api "" "pagerduty.com/service-id: PABC123" > "$CASE/catalog-info.yaml"
run_case oncall.sh
assert_eq "discovery off: the file isn't read, no query" "$(queried)" "none"
assert_eq "discovery off: service_lookup lists meta and input" \
  "$(svc_lookup)" '{"searched":["meta:pagerduty/service-id","input:service_id"]}'
assert_eq "service_lookup: .oncall.source names the tool" "$(got source)" '{"tool":"pagerduty","integration":"api"}'
assert_eq "service_lookup: no .oncall.service" "$(got service)" "null"
assert_eq "oncall never reads the Component JSON on push" "$(reads)" "0"
assert_eq "and says where else to map it" "$(logged 'backstage_discovery: "true", catalog-info.yaml. The from-backstage-collector sub-collector, if included')" "1"

new_case no-file
run_case oncall.sh "$FILE"
assert_eq "no catalog file: both candidate paths listed" \
  "$(svc_lookup | jq -c '.searched[2:]')" '["file:catalog-info.yaml (not found)","file:catalog-info.yml (not found)"]'

new_case bad-yaml
printf 'kind: [unclosed\n' > "$CASE/catalog-info.yaml"
run_case oncall.sh "$FILE"
assert_eq "unparseable catalog file: listed as such" \
  "$(svc_lookup | jq -c '.searched[2:]')" '["file:catalog-info.yaml (unparseable)"]'

new_case no-secret
catalog payment-api "" "pagerduty.com/service-id: PABC123" > "$CASE/catalog-info.yaml"
run_case oncall.sh "$FILE" LUNAR_SECRET_PAGERDUTY_API_KEY=
assert_eq "no PAGERDUTY_API_KEY: nothing written, no requests" \
  "$(writes) $(wc -l < "$CURL_LOG" | tr -d ' ')" "0 0"

new_case invalid-id
catalog payment-api "" "pagerduty.com/service-id: '../users?limit=100'" > "$CASE/catalog-info.yaml"
run_case oncall.sh "$FILE"
assert_eq "a value that isn't a PagerDuty ID is never sent" "$(queried) $(count pd.test)" "none 0"
assert_eq "but is recorded with where it came from" \
  "$(got service)" '{"id":"../users?limit=100","discovered_via":"file:catalog-info.yaml"}'

new_case pd-404
catalog payment-api "" "pagerduty.com/service-id: PGONE00" > "$CASE/catalog-info.yaml"
run_case oncall.sh "$FILE"
assert_eq "PagerDuty 404: the mapping is still recorded, with its source" \
  "$(got service)" '{"id":"PGONE00","discovered_via":"file:catalog-info.yaml"}'
assert_eq "PagerDuty 404: no service_lookup" "$(svc_lookup)" "null"

new_case bad-mode
catalog payment-api "" "pagerduty.com/service-id: PABC123" > "$CASE/catalog-info.yaml"
run_case oncall.sh LUNAR_VAR_BACKSTAGE_DISCOVERY=live
assert_eq "backstage_discovery other than true/false: warned, and the file isn't read" \
  "$(logged "backstage_discovery is 'live', but it takes") $(queried) $(svc_lookup | jq -c '.searched | length')" "1 none 2"

echo "from-backstage-collector sub-collector: the backstage collector's live lookup:"

for mode in by-name by-query; do
  BS=("LUNAR_VAR_REF_LOOKUP=$mode")

  new_case "$mode-component"
  catalog payment-api "" "" payment-platform > "$CASE/catalog-info.yaml"
  backstage_json "${BS[@]}"
  run_case from-backstage-collector.sh
  assert_eq "[$mode] the Component's own annotation" "$(queried) $(via)" "PCOMP01 component:default/payment-api"
  assert_eq "[$mode] no Backstage request from the pagerduty collector" "$(count bs.test)" "0"
  assert_eq "[$mode] the full service record is written" \
    "$(got service | jq -c '{id, status}') $(got summary | jq -c .has_oncall)" '{"id":"PCOMP01","status":"active"} true'

  new_case "$mode-system"
  catalog checkout "" "" payment-platform > "$CASE/catalog-info.yaml"
  backstage_json "${BS[@]}"
  run_case from-backstage-collector.sh
  assert_eq "[$mode] inherited from the System" "$(queried) $(via)" "PSYS001 system:default/payment-platform"

  new_case "$mode-domain"
  catalog ledger-api "" "" ledger-system > "$CASE/catalog-info.yaml"
  backstage_json "${BS[@]}"
  run_case from-backstage-collector.sh
  assert_eq "[$mode] inherited from the System's Domain" "$(queried) $(via)" "PDOM001 domain:default/finance"

  new_case "$mode-namespaces"
  catalog alpha ops "" platform/core > "$CASE/catalog-info.yaml"
  backstage_json "${BS[@]}"
  run_case from-backstage-collector.sh
  assert_eq "[$mode] qualified system ref, bare domain resolved in the System's namespace" \
    "$(queried) $(via)" "PDOMNS1 domain:platform/infra"

  new_case "$mode-miss"
  catalog orphan > "$CASE/catalog-info.yaml"
  backstage_json "${BS[@]}"
  run_case from-backstage-collector.sh
  assert_eq "[$mode] no annotation in the live catalog: service_lookup lists what it looked up" \
    "$(svc_lookup)" '{"searched":["component:default/orphan"]}'
  assert_eq "[$mode] and no PagerDuty query" "$(queried)" "none"

  new_case "$mode-quiet"
  catalog quiet "" "" standalone-system > "$CASE/catalog-info.yaml"
  backstage_json "${BS[@]}"
  run_case from-backstage-collector.sh
  assert_eq "[$mode] System with no annotation and no domain" \
    "$(svc_lookup | jq -c .searched)" '["component:default/quiet","system:default/standalone-system"]'

  new_case "$mode-dangling"
  catalog lonely "" "" ghost-system > "$CASE/catalog-info.yaml"
  backstage_json "${BS[@]}"
  run_case from-backstage-collector.sh
  assert_eq "[$mode] a System missing from the catalog is marked" \
    "$(svc_lookup | jq -c '.searched[1]')" '"system:default/ghost-system (not in catalog)"'

  new_case "$mode-unregistered"
  catalog not-registered "" "" payment-platform > "$CASE/catalog-info.yaml"
  backstage_json "${BS[@]}"
  run_case from-backstage-collector.sh
  assert_eq "[$mode] a Component missing from the catalog still inherits from its declared System" \
    "$(queried) $(via)" "PSYS001 system:default/payment-platform"

  for broken in five boom login notentity; do
    new_case "$mode-$broken"
    catalog "$broken" "" "" payment-platform > "$CASE/catalog-info.yaml"
    backstage_json "${BS[@]}"
    run_case from-backstage-collector.sh
    assert_eq "[$mode] a lookup that couldn't complete ($broken) is an error, not a miss" \
      "$(svc_lookup | jq -c '[(.errors | length), (.errors[0] | startswith("component:default/'"$broken"': ")), has("searched")]') $(queried) $(got service)" \
      '[1,true,false] none null'
  done
done

new_case file-in-live
catalog checkout "" "pagerduty.com/service-id: PFILE01" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case from-backstage-collector.sh
assert_eq "backstage_discovery off: the file isn't consulted, the live catalog answers" \
  "$(queried) $(via)" "PSYS001 system:default/payment-platform"

new_case custom-key
catalog checkout "" "" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case from-backstage-collector.sh LUNAR_VAR_BACKSTAGE_ANNOTATIONS=pagerduty/service-id
assert_eq "backstage_annotations narrows the keys read" "$(via)" "system:default/payment-platform"
run_case from-backstage-collector.sh LUNAR_VAR_BACKSTAGE_ANNOTATIONS=acme.com/pd
assert_eq "an annotation key no entity carries: Component, System and Domain listed" \
  "$(svc_lookup | jq -c .searched)" '["component:default/checkout","system:default/payment-platform","domain:default/finance"]'

new_case system-file
printf 'apiVersion: backstage.io/v1alpha1\nkind: System\nmetadata: {name: ledger-system}\nspec: {owner: t, domain: finance}\n' > "$CASE/catalog-info.yaml"
backstage_json
run_case from-backstage-collector.sh
assert_eq "a System catalog file inherits from its own Domain" "$(queried) $(via)" "PDOM001 domain:default/finance"

new_case live-meta
catalog payment-api "" "" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case from-backstage-collector.sh 'LUNAR_COMPONENT_META={"pagerduty/service-id":"PMETA01"}'
assert_eq "meta: left to oncall, nothing written, no read" "$(writes) $(reads)" "0 0"

new_case live-no-secret
catalog payment-api "" "" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case from-backstage-collector.sh LUNAR_SECRET_PAGERDUTY_API_KEY=
assert_eq "no PAGERDUTY_API_KEY: nothing read or written" "$(writes) $(reads)" "0 0"

echo "oncall and backstage together (one push):"

# Both sub-collectors run in the same case dir, so their writes add up the way
# Lunar merges them into one Component JSON.
new_case combo-file
catalog checkout "" "pagerduty.com/service-id: PFILE01" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case oncall.sh "$FILE"
run_case from-backstage-collector.sh "$FILE"
assert_eq "mapped in catalog-info.yaml: oncall collects it, backstage steps aside" \
  "$(queried) $(via) $(svc_lookup) $(logged 'which the oncall sub-collector reads')" \
  "PFILE01 file:catalog-info.yaml null 1"

new_case combo-inherited
catalog checkout "" "" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case oncall.sh "$FILE"
run_case from-backstage-collector.sh "$FILE"
assert_eq "inherited from the System: oncall misses the file, backstage collects it" \
  "$(queried) $(via)" "PSYS001 system:default/payment-platform"
assert_eq "oncall's miss stays recorded next to the service" \
  "$(svc_lookup)" '{"searched":["meta:pagerduty/service-id","input:service_id","file:catalog-info.yaml"]}'

# A monorepo component whose catalog entity lives in a shared ancestor file,
# found by the backstage collector's search_parent_dirs. oncall only reads the
# component's own directory, so the file's ID is not one it can collect, and
# backstage mustn't hand it off.
new_case combo-monorepo
echo "gitdir: $TEST_DIR/no-such-gitdir" > "$CASE/.git"
mkdir -p "$CASE/services/payments"
printf '%s\n' 'apiVersion: backstage.io/v1alpha1' 'kind: Component' 'metadata:' '  name: mono-payments' \
  '  annotations:' '    backstage.io/source-location: url:https://github.com/acme/mono/tree/main/services/payments/' \
  '    pagerduty.com/service-id: PMONO01' 'spec: {type: service, owner: t, lifecycle: production, system: payment-platform}' \
  > "$CASE/catalog-info.yaml"
CASE_CWD="$CASE/services/payments"
MONO=(LUNAR_COMPONENT_ID=github.com/acme/mono/services/payments)
backstage_json "${MONO[@]}" LUNAR_VAR_SEARCH_PARENT_DIRS=true LUNAR_VAR_MATCH_SOURCE_LOCATION=true
assert_eq "monorepo: the backstage collector read the shared ancestor file" \
  "$(jq -c '.catalog.native.backstage | [.path, .metadata.name]' "$CASE/component.json")" '["../../catalog-info.yaml","mono-payments"]'
run_case oncall.sh "$FILE" "${MONO[@]}"
run_case from-backstage-collector.sh "$FILE" "${MONO[@]}"
assert_eq "monorepo: oncall can't see that file, so backstage collects the live entity" \
  "$(queried) $(via)" "PMONO01 component:default/mono-payments"
assert_eq "monorepo: oncall's miss lists its own directory's file" \
  "$(svc_lookup | jq -c '.searched[2:]')" '["file:catalog-info.yaml (not found)","file:catalog-info.yml (not found)"]'

new_case combo-dotslash
catalog checkout "" "pagerduty.com/service-id: PFILE01" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case oncall.sh "$FILE" LUNAR_VAR_BACKSTAGE_CATALOG_PATHS=./catalog-info.yaml
run_case from-backstage-collector.sh "$FILE" LUNAR_VAR_BACKSTAGE_CATALOG_PATHS=./catalog-info.yaml
assert_eq "a ./-prefixed backstage_catalog_paths entry still hands off" \
  "$(queried) $(via)" "PFILE01 file:./catalog-info.yaml"

new_case combo-unmapped
catalog orphan > "$CASE/catalog-info.yaml"
backstage_json
run_case oncall.sh "$FILE"
run_case from-backstage-collector.sh "$FILE"
assert_eq "mapped nowhere: one list of every place looked" \
  "$(svc_lookup)" '{"searched":["meta:pagerduty/service-id","input:service_id","file:catalog-info.yaml","component:default/orphan"]}'

new_case combo-outage
catalog five "" "" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case oncall.sh "$FILE"
run_case from-backstage-collector.sh "$FILE"
assert_eq "Backstage failing: the error rides along with oncall's miss, so the check skips" \
  "$(svc_lookup | jq -c '{searched, errors: [.errors[] | sub(": .*"; "")]}')" \
  '{"searched":["meta:pagerduty/service-id","input:service_id","file:catalog-info.yaml"],"errors":["component:default/five"]}'

echo "Reading the Component JSON (retry, pinning):"

new_case pin
catalog checkout "" "" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case from-backstage-collector.sh
assert_eq "backstage: pinned to the commit the wave fired for" "$(cat "$CASE/getjson.log")" "github.com/acme/svc --git-sha abc123"
run_case from-backstage-collector.sh LUNAR_COMPONENT_PR=42
assert_eq "backstage: and to the PR on a PR" "$(tail -1 "$CASE/getjson.log")" "github.com/acme/svc --pr 42 --git-sha abc123"

new_case stale
catalog checkout "" "" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case from-backstage-collector.sh MOCK_GETJSON_FAIL=1 MOCK_GETJSON_STALE=2
assert_eq "a failed read, then two without the lookup, then it lands: resolves" \
  "$(queried) $(via) $(reads)" "PSYS001 system:default/payment-platform 4"
assert_eq "backing off 5s, 10s, 15s" "$(tr '\n' ' ' < "$CASE/sleeps")" "5 10 15 "
assert_eq "and saying how long it waited" "$(logged 'Waited 30s across 4 attempt(s)')" "1"
assert_eq "the get-json error is shown once, without its usage block" \
  "$(logged 'get-json: Error: rpc error') $(logged 'Usage:')" "1 0"

new_case budget
catalog checkout "" "" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case from-backstage-collector.sh MOCK_GETJSON_STALE=1000
assert_eq "the default budget is 1800s, backing off up to 60s" \
  "$(slept) $(longest_sleep) $(reads)" "1770 60 36"
assert_eq "a lookup that never becomes readable fails the run" "$CASE_EXIT $(writes)" "1 0"
assert_eq "and says why" "$(logged 'still isn.t readable after 1770s')" "1"

new_case budget-input
catalog checkout "" "" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case from-backstage-collector.sh MOCK_GETJSON_FAIL=1000 LUNAR_VAR_BACKSTAGE_WAIT_SECONDS=60
assert_eq "backstage_wait_seconds sets the budget" "$(slept) $(reads)" "50 5"
assert_eq "an unreadable Component JSON fails the run" "$CASE_EXIT $(writes) $(logged 'Could not read Component JSON')" "1 0 1"
run_case from-backstage-collector.sh MOCK_GETJSON_STALE=1 LUNAR_VAR_BACKSTAGE_WAIT_SECONDS=soon
assert_eq "an invalid backstage_wait_seconds falls back to 1800" \
  "$(logged "Invalid backstage_wait_seconds 'soon'") $(via)" "1 system:default/payment-platform"

echo "oncall-cron (default branch):"

new_case cron
catalog checkout "" "" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case oncall.sh "$CRON"
assert_eq "cron reads the live lookup from the default branch's JSON" "$(queried) $(via)" "PSYS001 system:default/payment-platform"
assert_eq "cron does not pin a sha" "$(cat "$CASE/getjson.log")" "github.com/acme/svc"

new_case cron-file
catalog checkout "" "pagerduty.com/service-id: PFILE01" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case oncall.sh "$CRON" "$FILE"
assert_eq "cron: the checked-out file first, no Component JSON read" "$(via) $(reads)" "file:catalog-info.yaml 0"

new_case cron-no-lookup
catalog checkout "" "" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case oncall.sh "$CRON" MOCK_GETJSON_STALE=1000
assert_eq "cron with no live lookup in the JSON: one read, no wait, service_lookup" \
  "$CASE_EXIT $(reads) $(slept) $(svc_lookup)" '0 1 0 {"searched":["meta:pagerduty/service-id","input:service_id"]}'

new_case cron-read-failed
catalog checkout "" "" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case oncall.sh "$CRON" MOCK_GETJSON_FAIL=1000
assert_eq "cron that can't read the JSON skips the refresh" "$CASE_EXIT $(writes) $(logged 'skipping this refresh')" "0 0 1"

new_case cron-outage
catalog five "" "" payment-platform > "$CASE/catalog-info.yaml"
backstage_json
run_case oncall.sh "$CRON"
assert_eq "cron: a lookup the backstage collector couldn't complete is an error" \
  "$(svc_lookup | jq -c '.errors | length') $(queried)" "1 none"

echo
if [ "$FAILS" -eq 0 ]; then
  echo "All pagerduty collector tests passed."
else
  echo "$FAILS test(s) failed."
  exit 1
fi
