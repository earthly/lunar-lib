#!/usr/bin/env bash
#
# Tests for codeowners.sh CODEOWNERS discovery — in particular the monorepo
# repo-root fallback (ENG-1248). Drives the real collector script with a stub
# `lunar` on PATH that captures the argv it was called with and any stdin
# payload, then asserts on what the collector reported.
#
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
COLLECTOR_DIR="$(dirname "$HERE")"
SCRIPT="$COLLECTOR_DIR/codeowners.sh"

PASS=0
FAIL=0

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    echo "PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $desc"
    echo "      expected: [$expected]"
    echo "      actual:   [$actual]"
    FAIL=$((FAIL + 1))
  fi
}

# ---------------------------------------------------------------------------
# Stub `lunar`: records argv to $LUNAR_CAPTURE; if the last arg is "-", the
# JSON payload arrives on stdin and is written to $LUNAR_PAYLOAD.
# ---------------------------------------------------------------------------
make_stub_lunar() {
  local dir="$1"
  cat > "$dir/lunar" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$LUNAR_CAPTURE"
if [ "${!#}" = "-" ]; then
  cat > "$LUNAR_PAYLOAD"
fi
STUB
  chmod +x "$dir/lunar"
}

# A `git` stub that always fails, to exercise the non-git walk-up fallback.
make_stub_failing_git() {
  local dir="$1"
  cat > "$dir/git" <<'STUB'
#!/usr/bin/env bash
exit 1
STUB
  chmod +x "$dir/git"
}

STUBS="$(mktemp -d)"
make_stub_lunar "$STUBS"

STUBS_NOGIT="$(mktemp -d)"
make_stub_lunar "$STUBS_NOGIT"
make_stub_failing_git "$STUBS_NOGIT"

DEFAULT_PATHS="CODEOWNERS,.github/CODEOWNERS,docs/CODEOWNERS"

# run_collector <stubs_dir> <cwd> [scope]
# Sets up capture files and runs codeowners.sh; leaves results in
# $CAP_ARGS (argv lines) and $CAP_PAYLOAD (json payload, if any).
run_collector() {
  local stubs="$1" cwd="$2" scope="${3:-}"
  local work; work="$(mktemp -d)"
  CAP_ARGS="$work/args"
  CAP_PAYLOAD="$work/payload"
  : > "$CAP_ARGS"
  : > "$CAP_PAYLOAD"
  (
    cd "$cwd" || exit 1
    export PATH="$stubs:$PATH"
    export LUNAR_CAPTURE="$CAP_ARGS"
    export LUNAR_PAYLOAD="$CAP_PAYLOAD"
    export LUNAR_VAR_CODEOWNERS_PATHS="$DEFAULT_PATHS"
    if [ -n "$scope" ]; then
      export LUNAR_VAR_CODEOWNERS_SCOPE="$scope"
    else
      unset LUNAR_VAR_CODEOWNERS_SCOPE
    fi
    bash "$SCRIPT"
  )
}

field() { jq -r "$1" "$CAP_PAYLOAD" 2>/dev/null; }

# ---------------------------------------------------------------------------
# 1. Single repo, CODEOWNERS at root (CWD == repo root)
# ---------------------------------------------------------------------------
single_repo_root() {
  local root; root="$(mktemp -d)"
  git -C "$root" init -q
  printf '* @acme/platform\n' > "$root/CODEOWNERS"
  run_collector "$STUBS" "$root"
  assert_eq "single-repo root: exists" "true" "$(field .exists)"
  assert_eq "single-repo root: scope" "repo" "$(field .scope)"
  assert_eq "single-repo root: path" "CODEOWNERS" "$(field .path)"
}

# ---------------------------------------------------------------------------
# 2. Single repo, .github/CODEOWNERS
# ---------------------------------------------------------------------------
single_repo_github() {
  local root; root="$(mktemp -d)"
  git -C "$root" init -q
  mkdir -p "$root/.github"
  printf '* @acme/platform\n' > "$root/.github/CODEOWNERS"
  run_collector "$STUBS" "$root"
  assert_eq "single-repo .github: exists" "true" "$(field .exists)"
  assert_eq "single-repo .github: scope" "repo" "$(field .scope)"
  assert_eq "single-repo .github: path" ".github/CODEOWNERS" "$(field .path)"
}

# ---------------------------------------------------------------------------
# 3. Monorepo subcomponent, GLOBAL CODEOWNERS at repo root, auto (THE FIX)
# ---------------------------------------------------------------------------
monorepo_global_auto() {
  local root; root="$(mktemp -d)"
  git -C "$root" init -q
  mkdir -p "$root/.github" "$root/services/backend"
  printf '* @acme/platform\n/services/backend/ @acme/backend\n' > "$root/.github/CODEOWNERS"
  run_collector "$STUBS" "$root/services/backend"
  assert_eq "monorepo global (auto): exists" "true" "$(field .exists)"
  assert_eq "monorepo global (auto): scope" "repo" "$(field .scope)"
  assert_eq "monorepo global (auto): path" ".github/CODEOWNERS" "$(field .path)"
}

# ---------------------------------------------------------------------------
# 4. Monorepo subcomponent with its own CODEOWNERS, auto -> component scope
# ---------------------------------------------------------------------------
monorepo_component_auto() {
  local root; root="$(mktemp -d)"
  git -C "$root" init -q
  mkdir -p "$root/.github" "$root/services/backend"
  printf '* @acme/platform\n' > "$root/.github/CODEOWNERS"
  printf '* @acme/backend\n' > "$root/services/backend/CODEOWNERS"
  run_collector "$STUBS" "$root/services/backend"
  assert_eq "monorepo component (auto): exists" "true" "$(field .exists)"
  assert_eq "monorepo component (auto): scope" "component" "$(field .scope)"
  assert_eq "monorepo component (auto): path" "services/backend/CODEOWNERS" "$(field .path)"
}

# ---------------------------------------------------------------------------
# 5. Monorepo subcomponent, no CODEOWNERS anywhere -> exists:false
# ---------------------------------------------------------------------------
monorepo_none() {
  local root; root="$(mktemp -d)"
  git -C "$root" init -q
  mkdir -p "$root/services/backend"
  run_collector "$STUBS" "$root/services/backend"
  local args; args="$(cat "$CAP_ARGS")"
  if printf '%s' "$args" | grep -qF -- "-j .ownership.codeowners.exists false"; then
    echo "PASS: monorepo none: reports exists=false"
    PASS=$((PASS + 1))
  else
    echo "FAIL: monorepo none: reports exists=false"
    echo "      captured args: [$args]"
    FAIL=$((FAIL + 1))
  fi
}

# ---------------------------------------------------------------------------
# 6. scope=repo-root ignores a component-dir file and uses the global one
# ---------------------------------------------------------------------------
scope_repo_root_forces_global() {
  local root; root="$(mktemp -d)"
  git -C "$root" init -q
  mkdir -p "$root/services/backend"
  printf '* @acme/platform\n' > "$root/CODEOWNERS"
  printf '* @acme/backend\n' > "$root/services/backend/CODEOWNERS"
  run_collector "$STUBS" "$root/services/backend" "repo-root"
  assert_eq "scope=repo-root: exists" "true" "$(field .exists)"
  assert_eq "scope=repo-root: scope" "repo" "$(field .scope)"
  assert_eq "scope=repo-root: path" "CODEOWNERS" "$(field .path)"
}

# ---------------------------------------------------------------------------
# 7. scope=component-dir ignores the global file (pre-monorepo behavior)
# ---------------------------------------------------------------------------
scope_component_dir_ignores_global() {
  local root; root="$(mktemp -d)"
  git -C "$root" init -q
  mkdir -p "$root/.github" "$root/services/backend"
  printf '* @acme/platform\n' > "$root/.github/CODEOWNERS"
  run_collector "$STUBS" "$root/services/backend" "component-dir"
  local args; args="$(cat "$CAP_ARGS")"
  if printf '%s' "$args" | grep -qF -- "-j .ownership.codeowners.exists false"; then
    echo "PASS: scope=component-dir: ignores global -> exists=false"
    PASS=$((PASS + 1))
  else
    echo "FAIL: scope=component-dir: ignores global -> exists=false"
    echo "      captured args: [$args]"
    FAIL=$((FAIL + 1))
  fi
}

# ---------------------------------------------------------------------------
# 8. No git binary: walk-up fallback still finds the repo-root .git + global
# ---------------------------------------------------------------------------
no_git_fallback() {
  local root; root="$(mktemp -d)"
  mkdir -p "$root/.git" "$root/.github" "$root/services/backend"
  printf '* @acme/platform\n' > "$root/.github/CODEOWNERS"
  run_collector "$STUBS_NOGIT" "$root/services/backend"
  assert_eq "no-git fallback: exists" "true" "$(field .exists)"
  assert_eq "no-git fallback: scope" "repo" "$(field .scope)"
  assert_eq "no-git fallback: path" ".github/CODEOWNERS" "$(field .path)"
}

single_repo_root
single_repo_github
monorepo_global_auto
monorepo_component_auto
monorepo_none
scope_repo_root_forces_global
scope_component_dir_ignores_global
no_git_fallback

echo
echo "-------------------------------------"
echo "codeowners.sh finder: $PASS passed, $FAIL failed"
if [ "$FAIL" -ne 0 ]; then
  exit 1
fi
