#!/bin/bash
#
# Local offline test for the pagerduty collector's Backstage-discovery mode.
#
# The cron hook runs with clone-code: true, so the collector reads
# catalog-info.yaml from the checked-out repo (its working directory). This
# test stages a catalog-info.yaml in a per-case dir, runs oncall.sh from
# there, and mocks:
#   - `curl` — the PagerDuty REST API only (records the requested service ID,
#     returns a minimal service JSON). No GitHub calls: discovery reads the
#     local checkout, not the API.
#   - `lunar` — captures `lunar collect -j <path> -` writes to per-path files.
#
# Asserts that discovery resolves the service ID from the annotation and drives
# the PagerDuty query (`.oncall.service.id`), plus precedence / opt-in / missing
# -file behaviour.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURES_DIR="$SCRIPT_DIR/test/fixtures"
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# --- Mock curl (PagerDuty API only) ---------------------------------------
cat > "$TEST_DIR/curl" << 'EOF'
#!/bin/bash
set -uo pipefail
D="${MOCK_DIR:?}"
URL=""
while [ $# -gt 0 ]; do
  case "$1" in
    -H|-w|-o) shift 2 ;;
    http://*|https://*) URL="$1"; shift ;;
    -*) shift ;;
    *) shift ;;
  esac
done
case "$URL" in
  */services/P*)
    sid="${URL##*/services/}"; sid="${sid%%\?*}"
    printf '%s' "$sid" > "$D/requested_service"
    printf '{"service":{"name":"Test Service","status":"active"}}'
    exit 0
    ;;
  *)
    echo "mock curl: unhandled URL: $URL" >&2
    exit 1
    ;;
esac
EOF
chmod +x "$TEST_DIR/curl"

# --- Mock lunar -----------------------------------------------------------
cat > "$TEST_DIR/lunar" << 'EOF'
#!/bin/bash
set -uo pipefail
D="${MOCK_DIR:?}"
if [ "${1:-}" = "collect" ] && [ "${2:-}" = "-j" ]; then
  path="${3:-unknown}"
  safe="${path//[^a-zA-Z0-9]/_}"
  cat >> "$D/collect${safe}.out"
  exit 0
fi
exit 0
EOF
chmod +x "$TEST_DIR/lunar"

export PATH="$TEST_DIR:$PATH"

PASS=0; FAIL=0

# run_case <name> <fixture-or-NONE> <expected-service-id-or-NONE> <env KEY=VAL ...>
run_case() {
  local name="$1" fixture="$2" expected="$3"; shift 3
  local casedir="$TEST_DIR/$name"
  mkdir -p "$casedir"
  export MOCK_DIR="$casedir"

  # Stage the checkout: a catalog-info.yaml in the case dir (the cwd), or none.
  [ "$fixture" != "NONE" ] && cp "$FIXTURES_DIR/$fixture.yaml" "$casedir/catalog-info.yaml"

  # Reset collector env each case.
  unset LUNAR_VAR_BACKSTAGE_DISCOVERY LUNAR_VAR_BACKSTAGE_ANNOTATIONS \
        LUNAR_VAR_BACKSTAGE_CATALOG_PATHS LUNAR_VAR_SERVICE_ID LUNAR_COMPONENT_META
  export LUNAR_COMPONENT_ID="github.com/acme/payment-api"
  export LUNAR_SECRET_PAGERDUTY_API_KEY="pd-test-key"

  local kv
  for kv in "$@"; do export "${kv?}"; done

  echo "── case: $name ──"
  ( cd "$casedir" && bash "$SCRIPT_DIR/oncall.sh" ) > "$casedir/stdout" 2> "$casedir/stderr" || {
    echo "  FAIL — oncall.sh exited non-zero"; echo "    $(tail -1 "$casedir/stderr")"; FAIL=$((FAIL+1)); return
  }

  local got_service="" got_id=""
  [ -f "$casedir/requested_service" ] && got_service="$(cat "$casedir/requested_service")"
  [ -f "$casedir/collect_oncall_service.out" ] && \
    got_id="$(jq -r '.id // empty' "$casedir/collect_oncall_service.out" 2>/dev/null || echo "")"

  if [ "$expected" = "NONE" ]; then
    if [ -z "$got_service" ]; then
      echo "  OK (no PagerDuty query, as expected)"; PASS=$((PASS+1))
    else
      echo "  FAIL — expected no query, but service '$got_service' was requested"; FAIL=$((FAIL+1))
    fi
  else
    if [ "$got_service" = "$expected" ] && [ "$got_id" = "$expected" ]; then
      echo "  OK (resolved + queried service '$expected'; .oncall.service.id='$got_id')"; PASS=$((PASS+1))
    else
      echo "  FAIL — expected '$expected'; queried='$got_service', .oncall.service.id='$got_id'"; FAIL=$((FAIL+1))
    fi
  fi
}

# 1. Discovery reads pagerduty.com/service-id from the checked-out file.
run_case "discover_dotcom" "catalog-info-dotcom" "PABC123" \
  LUNAR_VAR_BACKSTAGE_DISCOVERY=true

# 2. Discovery reads the lunar-style pagerduty/service-id key (2nd in list),
#    skipping the non-Component (System) doc in a multi-doc file.
run_case "discover_lunarkey" "catalog-info-lunarkey" "PDEF456" \
  LUNAR_VAR_BACKSTAGE_DISCOVERY=true

# 3. Explicit service_id input wins over discovery.
run_case "input_wins" "catalog-info-dotcom" "PINPUT9" \
  LUNAR_VAR_BACKSTAGE_DISCOVERY=true LUNAR_VAR_SERVICE_ID=PINPUT9

# 4. Discovery off (default) → no discovery, no query.
run_case "discovery_off" "catalog-info-dotcom" "NONE"

# 5. Discovery on but no catalog-info.yaml in the checkout → clean skip.
run_case "no_file" "NONE" "NONE" \
  LUNAR_VAR_BACKSTAGE_DISCOVERY=true

echo ""
echo "=========================================="
echo "Passed: $PASS  Failed: $FAIL"
echo "=========================================="
[ "$FAIL" -eq 0 ]
