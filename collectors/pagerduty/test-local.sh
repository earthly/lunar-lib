#!/bin/bash
#
# Local offline test for the pagerduty collector's Backstage-discovery mode.
#
# Mocks:
#   - `curl` for BOTH call styles the collector uses:
#       * GitHub Contents API (`-o <file> -w '%{http_code}'`) — serves a
#         per-scenario catalog-info fixture, or 404 when none is set.
#       * PagerDuty REST API (`-fsS ... <url>`) — records the requested
#         service ID and returns a minimal service JSON.
#   - `lunar` — captures `lunar collect -j <path> -` writes to per-path files.
#
# Then asserts that discovery resolves the service ID from the annotation and
# drives the PagerDuty query (`.oncall.service.id`), and that the opt-in /
# precedence / no-token behaviours hold.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURES_DIR="$SCRIPT_DIR/test/fixtures"
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# --- Mock curl ------------------------------------------------------------
cat > "$TEST_DIR/curl" << 'EOF'
#!/bin/bash
set -uo pipefail
D="${MOCK_DIR:?}"
OUT=""; URL=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) OUT="$2"; shift 2 ;;
    -H|-w) shift 2 ;;
    http://*|https://*) URL="$1"; shift ;;
    -*) shift ;;
    *) shift ;;
  esac
done

case "$URL" in
  *api.github.com/repos/*/contents/*)
    # GitHub Contents API style: body → OUT, http code → stdout.
    if [ -n "${MOCK_CATALOG_FILE:-}" ] && [ -f "${MOCK_CATALOG_FILE:-}" ] \
       && [[ "$URL" == *"/contents/catalog-info.yaml"* ]]; then
      cat "$MOCK_CATALOG_FILE" > "$OUT"
      printf '200'
    else
      printf '{"message":"Not Found"}' > "$OUT"
      printf '404'
    fi
    exit 0
    ;;
  *api.pagerduty.com/services/*|*/services/P*)
    # PagerDuty service fetch: record the requested ID, return minimal JSON.
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

# run_case <name> <expected-service-id-or-NONE> <env KEY=VAL ...>
run_case() {
  local name="$1" expected="$2"; shift 2
  local casedir="$TEST_DIR/$name"
  mkdir -p "$casedir"
  export MOCK_DIR="$casedir"

  # Reset collector env each case. Also clear any ambient GH_TOKEN so the
  # no-token case is genuinely token-less (the discover fn falls back to a
  # bare GH_TOKEN env var when LUNAR_SECRET_GH_TOKEN is unset).
  unset LUNAR_VAR_BACKSTAGE_DISCOVERY LUNAR_VAR_BACKSTAGE_ANNOTATIONS \
        LUNAR_VAR_BACKSTAGE_CATALOG_PATHS LUNAR_VAR_BACKSTAGE_BRANCH \
        LUNAR_VAR_SERVICE_ID LUNAR_COMPONENT_META MOCK_CATALOG_FILE GH_TOKEN
  export LUNAR_COMPONENT_ID="github.com/acme/payment-api"
  export LUNAR_SECRET_PAGERDUTY_API_KEY="pd-test-key"
  export LUNAR_SECRET_GH_TOKEN="gh-test-token"

  local kv
  for kv in "$@"; do
    if [ "$kv" = "UNSET_GH_TOKEN" ]; then unset LUNAR_SECRET_GH_TOKEN; else export "${kv?}"; fi
  done

  echo "── case: $name ──"
  bash "$SCRIPT_DIR/oncall.sh" > "$casedir/stdout" 2> "$casedir/stderr" || {
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

# 1. Discovery resolves the pagerduty.com/service-id annotation.
run_case "discover_dotcom" "PABC123" \
  LUNAR_VAR_BACKSTAGE_DISCOVERY=true "MOCK_CATALOG_FILE=$FIXTURES_DIR/catalog-info-dotcom.yaml"

# 2. Discovery resolves the lunar-style pagerduty/service-id key (2nd in list),
#    and skips the non-Component (System) doc in a multi-doc file.
run_case "discover_lunarkey" "PDEF456" \
  LUNAR_VAR_BACKSTAGE_DISCOVERY=true "MOCK_CATALOG_FILE=$FIXTURES_DIR/catalog-info-lunarkey.yaml"

# 3. Explicit service_id input wins over discovery (discovery not consulted).
run_case "input_wins" "PINPUT9" \
  LUNAR_VAR_BACKSTAGE_DISCOVERY=true LUNAR_VAR_SERVICE_ID=PINPUT9 \
  "MOCK_CATALOG_FILE=$FIXTURES_DIR/catalog-info-dotcom.yaml"

# 4. Discovery enabled but no GH_TOKEN → skip cleanly, no query.
run_case "no_token" "NONE" \
  LUNAR_VAR_BACKSTAGE_DISCOVERY=true UNSET_GH_TOKEN \
  "MOCK_CATALOG_FILE=$FIXTURES_DIR/catalog-info-dotcom.yaml"

# 5. Discovery off (default) → no discovery, no query.
run_case "discovery_off" "NONE" \
  "MOCK_CATALOG_FILE=$FIXTURES_DIR/catalog-info-dotcom.yaml"

echo ""
echo "=========================================="
echo "Passed: $PASS  Failed: $FAIL"
echo "=========================================="
[ "$FAIL" -eq 0 ]
