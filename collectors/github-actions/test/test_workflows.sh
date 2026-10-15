#!/usr/bin/env bash
#
# Tests for where workflows.sh finds .github/workflows, in particular the
# monorepo repo-root fallback. Drives the real collector against fabricated
# repo layouts with a stub `lunar` that saves each `lunar collect -j <path> -`
# payload to $OUT/<path>.json.
#
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$(dirname "$HERE")/workflows.sh"

PASS=0
FAIL=0

check() {
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

STUBS="$(mktemp -d)"
cat > "$STUBS/lunar" <<'STUB'
#!/usr/bin/env bash
cat > "$LUNAR_OUT/$3.json"
STUB
chmod +x "$STUBS/lunar"

# The same plus a git that always fails, as in an image without git.
STUBS_NOGIT="$(mktemp -d)"
cp "$STUBS/lunar" "$STUBS_NOGIT/lunar"
printf '#!/usr/bin/env bash\nexit 1\n' > "$STUBS_NOGIT/git"
chmod +x "$STUBS_NOGIT/git"

# run <stubs> <cwd>
run() {
  OUT="$(mktemp -d)"
  (cd "$2" && PATH="$1:$PATH" LUNAR_OUT="$OUT" LUNAR_COMPONENT_ID="github.com/acme/mono" bash "$SCRIPT") 2>/dev/null
}

# The workflow files the collector recorded, comma-joined.
files() { jq -r '[.workflows[].file] | join(",")' "$OUT/.ci.native.github_actions.json" 2>/dev/null; }
written() {
  local f names=()
  for f in "$OUT"/.[!.]* "$OUT"/*; do
    [ -e "$f" ] && names+=("${f##*/}")
  done
  (IFS=,; printf '%s' "${names[*]}")
}

add_workflow() {
  mkdir -p "$1/.github/workflows"
  printf 'name: %s\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n' \
    "$2" > "$1/.github/workflows/$2.yml"
}

# A repo with one subdirectory component, apps/gadget.
new_repo() {
  local d; d="$(mktemp -d)"
  git -C "$d" init -q
  mkdir -p "$d/apps/gadget"
  printf '%s\n' "$d"
}

r="$(new_repo)"; add_workflow "$r" ci
run "$STUBS" "$r"
check "single repo: reads its workflows" ".github/workflows/ci.yml" "$(files)"

r="$(new_repo)"; add_workflow "$r" build
run "$STUBS" "$r/apps/gadget"
check "monorepo subdir: falls back to the root's workflows" ".github/workflows/build.yml" "$(files)"
check "monorepo subdir: writes all three paths" ".ci.dependencies.json,.ci.lint.json,.ci.native.github_actions.json" "$(written)"
check "monorepo subdir: counts the root's actions" "1" "$(jq -r .total "$OUT/.ci.dependencies.json" 2>/dev/null)"

r="$(new_repo)"; add_workflow "$r" build; add_workflow "$r/apps/gadget" gadget
run "$STUBS" "$r/apps/gadget"
check "monorepo subdir with its own workflows: keeps them" ".github/workflows/gadget.yml" "$(files)"

r="$(new_repo)"
run "$STUBS" "$r/apps/gadget"
check "no workflows anywhere: writes nothing" "" "$(written)"

# The hub's per-snippet checkout is a git worktree, so .git is a file.
r="$(mktemp -d)"; printf 'gitdir: /nonexistent\n' > "$r/.git"; mkdir -p "$r/apps/gadget"; add_workflow "$r" build
run "$STUBS_NOGIT" "$r/apps/gadget"
check "no git binary: walks up to the .git file" ".github/workflows/build.yml" "$(files)"

# Without a .git entry there is no known repo root, so it doesn't climb.
r="$(mktemp -d)"; mkdir -p "$r/apps/gadget"; add_workflow "$r" build
run "$STUBS_NOGIT" "$r/apps/gadget"
check "no repo root: doesn't read a parent's workflows" "" "$(written)"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
