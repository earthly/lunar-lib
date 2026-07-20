#!/bin/bash
#
# Local offline test for the Backstage collector's referential-integrity
# feature. Mocks `curl` (against the Backstage catalog by-name API) and
# `lunar` (capturing the collected `.catalog.native.backstage` write) so the
# collector can be exercised end-to-end without network access.
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

# --- Mock curl: emit an http_code based on the requested entity name -------
cat > "$MOCK/curl" << 'EOF'
#!/bin/bash
url="${@: -1}"
name="${url##*/}"
case "$name" in
  boom)  exit 7 ;;
  five)  echo -n "502"; exit 0 ;;
  typo*) echo -n "404"; exit 0 ;;
  *)     echo -n "200"; exit 0 ;;
esac
EOF
chmod +x "$MOCK/curl"

# --- Mock lunar: capture stdin (the collected JSON) -----------------------
printf '#!/bin/bash\ncat\n' > "$MOCK/lunar"
chmod +x "$MOCK/lunar"

# Run main.sh in a fresh workdir with a crafted catalog-info.yaml, echoing the
# collected `.refs` object (or `null` when none was written).
run() {
  local domain="$1" system="$2" url="$3" ns="${4:-}"
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
    [ -n "$domain" ] && echo "  domain: $domain"
    [ -n "$system" ] && echo "  system: $system"
  } > "$wd/catalog-info.yaml"
  ( cd "$wd" \
    && PATH="$MOCK:$PATH" \
       LUNAR_VAR_PATHS="catalog-info.yaml,catalog-info.yml" \
       LUNAR_VAR_BACKSTAGE_URL="$url" \
       LUNAR_SECRET_BACKSTAGE_TOKEN="test-token" \
       bash "$SCRIPT_DIR/main.sh" ) | jq -c '.refs'
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

if [ "$FAILS" -eq 0 ]; then
  echo "All referential-integrity tests passed."
else
  echo "$FAILS test(s) failed."
  exit 1
fi
