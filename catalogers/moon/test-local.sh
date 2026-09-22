#!/bin/bash
#
# Offline test for the moon cataloger. Builds real moon workspaces in a temp
# dir, stubs `lunar` on PATH to capture the catalog write, and drives main.sh
# as a subprocess. Needs the real `moon` binary, which is why the Earthfile
# `test` target runs on +image rather than a bare alpine.
#
# Run it in the image (`earthly ./catalogers/moon+test`), not on your host: the
# script does path arithmetic on BusyBox in the shipped image, and green on a
# GNU host proves nothing about that.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR=$(mktemp -d)
STUB_DIR="$TEST_DIR/stub"
WRITE_OUT="$TEST_DIR/write.json"
FAILED=0

trap 'rm -rf "$TEST_DIR"' EXIT

git config --global --add safe.directory '*' 2>/dev/null || true

# --- Stub lunar -----------------------------------------------------------
# Captures the JSON piped to `lunar catalog raw --json .components -`.
mkdir -p "$STUB_DIR"
cat > "$STUB_DIR/lunar" << 'STUB'
#!/bin/bash
set -uo pipefail
if [ "${1:-}" = "catalog" ]; then
    cat > "${MOCK_WRITE_OUT:?MOCK_WRITE_OUT unset}"
    exit 0
fi
echo "Mock lunar: unhandled command: $*" >&2
exit 1
STUB
chmod +x "$STUB_DIR/lunar"
export PATH="$STUB_DIR:$PATH"
export MOCK_WRITE_OUT="$WRITE_OUT"

# --- Fixture --------------------------------------------------------------
# web depends on telemetry only, so packages/auth can only reach it
# transitively — that edge is the whole feature.
#   apps/fleet-api  -> auth, telemetry
#   apps/web        -> telemetry -> auth
#   packages/telemetry -> auth
#   packages/auth   -> (leaf)
#   tools/lint      -> auth  (development scope)
make_workspace() {
    local root="$1" nest="${2:-}"
    local ws="$root${nest:+/$nest}"
    mkdir -p "$ws"/{apps/fleet-api,apps/web,packages/auth,packages/telemetry,tools/lint} "$ws/.moon"
    printf "projects:\n  - 'apps/*'\n  - 'packages/*'\n  - 'tools/*'\n" > "$ws/.moon/workspace.yml"
    printf "layer: application\nlanguage: javascript\ndependsOn: [auth, telemetry]\n" > "$ws/apps/fleet-api/moon.yml"
    printf "layer: application\nlanguage: javascript\ndependsOn: [telemetry]\n"      > "$ws/apps/web/moon.yml"
    printf "layer: library\nlanguage: javascript\ndependsOn: [auth]\n"               > "$ws/packages/telemetry/moon.yml"
    printf "layer: library\nlanguage: javascript\n"                                  > "$ws/packages/auth/moon.yml"
    printf "layer: tool\nlanguage: javascript\ndependsOn:\n  - id: 'auth'\n    scope: 'development'\n" > "$ws/tools/lint/moon.yml"
    ( cd "$root" && git init -q . && git add -A && \
      git -c user.email=t@t -c user.name=t commit -qm init ) >/dev/null
}

# run <cwd> <component-id> [VAR=value ...] -> stdout+stderr, sets RUN_EXIT
run() {
    local cwd="$1" cid="$2"; shift 2
    rm -f "$WRITE_OUT"
    RUN_OUT=$( cd "$cwd" && env LUNAR_COMPONENT_ID="$cid" "$@" bash "$SCRIPT_DIR/main.sh" 2>&1 )
    RUN_EXIT=$?
}

pass() { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; FAILED=1; }

# assert_paths <expected-json-array>
assert_paths() {
    local want="$1" got
    if [ ! -f "$WRITE_OUT" ]; then fail "no catalog write (expected $want)"; return; fi
    got=$(jq -c '[.[] | .paths] | first' "$WRITE_OUT")
    if [ "$got" = "$want" ]; then pass "paths = $want"; else fail "paths: want $want, got $got"; fi
}

WS="$TEST_DIR/repo"
make_workspace "$WS"

echo "Scenario 1: transitive closure (web -> telemetry -> auth)"
run "$WS/apps/web" "github.com/acme/mono/apps/web"
assert_paths '["apps/web/*","packages/auth/*","packages/telemetry/*"]'

echo "Scenario 2: direct + transitive both present (fleet-api)"
run "$WS/apps/fleet-api" "github.com/acme/mono/apps/fleet-api"
assert_paths '["apps/fleet-api/*","packages/auth/*","packages/telemetry/*"]'

echo "Scenario 3: leaf library gets only its own directory"
run "$WS/packages/auth" "github.com/acme/mono/packages/auth"
assert_paths '["packages/auth/*"]'

echo "Scenario 4: exclude_scopes drops a development edge"
run "$WS/tools/lint" "github.com/acme/mono/tools/lint"
assert_paths '["packages/auth/*","tools/lint/*"]'
run "$WS/tools/lint" "github.com/acme/mono/tools/lint" LUNAR_VAR_EXCLUDE_SCOPES=development
assert_paths '["tools/lint/*"]'

echo "Scenario 5: repo-root component skips (writing paths would narrow it)"
run "$WS" "github.com/acme/mono"
if [ "$RUN_EXIT" -eq 0 ] && [ ! -f "$WRITE_OUT" ]; then pass "exit 0, no write"; else fail "exit=$RUN_EXIT write=$([ -f "$WRITE_OUT" ] && echo yes || echo no)"; fi

echo "Scenario 6: subdir that is not a moon project skips"
mkdir -p "$WS/docs"
run "$WS/docs" "github.com/acme/mono/docs"
if [ "$RUN_EXIT" -eq 0 ] && [ ! -f "$WRITE_OUT" ]; then pass "exit 0, no write"; else fail "exit=$RUN_EXIT write=$([ -f "$WRITE_OUT" ] && echo yes || echo no)"; fi

echo "Scenario 7: repo with no .moon/ skips"
NOMOON="$TEST_DIR/nomoon"; mkdir -p "$NOMOON/svc"; echo x > "$NOMOON/svc/a.txt"
( cd "$NOMOON" && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -qm init ) >/dev/null
run "$NOMOON/svc" "github.com/acme/plain/svc"
if [ "$RUN_EXIT" -eq 0 ] && [ ! -f "$WRITE_OUT" ]; then pass "exit 0, no write"; else fail "exit=$RUN_EXIT write=$([ -f "$WRITE_OUT" ] && echo yes || echo no)"; fi

echo "Scenario 8: nested workspace prefixes every path with its offset"
NEST="$TEST_DIR/nested"
make_workspace "$NEST" "frontend"
run "$NEST/frontend/apps/web" "github.com/acme/nest/frontend/apps/web"
assert_paths '["frontend/apps/web/*","frontend/packages/auth/*","frontend/packages/telemetry/*"]'

echo "Scenario 9: edgeless multi-project graph fails closed"
ZERO="$TEST_DIR/zero"; mkdir -p "$ZERO"/{apps/a,apps/b} "$ZERO/.moon"
printf "projects:\n  - 'apps/*'\n" > "$ZERO/.moon/workspace.yml"
printf "layer: application\nlanguage: javascript\n" > "$ZERO/apps/a/moon.yml"
printf "layer: library\nlanguage: javascript\n"     > "$ZERO/apps/b/moon.yml"
( cd "$ZERO" && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -qm init ) >/dev/null
run "$ZERO/apps/a" "github.com/acme/z/apps/a"
if [ "$RUN_EXIT" -ne 0 ] && [ ! -f "$WRITE_OUT" ]; then pass "exit $RUN_EXIT, no write"; else fail "expected non-zero exit and no write, got exit=$RUN_EXIT"; fi
if echo "$RUN_OUT" | grep -q "nothing depends on anything"; then pass "explains why it refused"; else fail "missing explanation"; fi

echo "Scenario 10: require_dependency_edges=false allows the edgeless graph"
run "$ZERO/apps/a" "github.com/acme/z/apps/a" LUNAR_VAR_REQUIRE_DEPENDENCY_EDGES=false
assert_paths '["apps/a/*"]'

echo ""
if [ "$FAILED" -eq 0 ]; then echo "All scenarios passed"; else echo "FAILURES"; fi
exit "$FAILED"
