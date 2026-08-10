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

if [ "$FAILS" -eq 0 ]; then
  echo "All referential-integrity tests passed."
else
  echo "$FAILS test(s) failed."
  exit 1
fi
