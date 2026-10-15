#!/usr/bin/env bash
#
# Tests for which .github/workflows workflows.sh reads (the repository root's,
# the only ones GitHub runs) and for recording actionlint's findings. Drives
# the real collector against fabricated repo layouts with a stub `lunar` that
# saves each `lunar collect -j <path> -` payload to $OUT/<path>.json.
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
lint() { jq -r "$1" "$OUT/.ci.lint.json" 2>/dev/null; }
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

# A workflow actionlint rejects: "bogus" is not a job key.
add_broken_workflow() {
  mkdir -p "$1/.github/workflows"
  printf 'name: %s\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    bogus: 1\n    steps:\n      - run: echo hi\n' \
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
check "monorepo subdir: reads the root's workflows" ".github/workflows/build.yml" "$(files)"
check "monorepo subdir: writes all three paths" ".ci.dependencies.json,.ci.lint.json,.ci.native.github_actions.json" "$(written)"
check "monorepo subdir: counts the root's actions" "1" "$(jq -r .total "$OUT/.ci.dependencies.json" 2>/dev/null)"

# A subdirectory's own .github/workflows never runs on GitHub.
r="$(new_repo)"; add_workflow "$r" build; add_workflow "$r/apps/gadget" gadget
run "$STUBS" "$r/apps/gadget"
check "monorepo subdir with its own workflows: still reads the root's" ".github/workflows/build.yml" "$(files)"

r="$(new_repo)"; add_workflow "$r/apps/gadget" gadget
run "$STUBS" "$r/apps/gadget"
check "workflows only in the subdir: writes nothing" "" "$(written)"

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

r="$(mktemp -d)"; add_workflow "$r" own
run "$STUBS_NOGIT" "$r"
check "no repo root: reads its own workflows" ".github/workflows/own.yml" "$(files)"

if command -v actionlint >/dev/null; then
  r="$(new_repo)"; add_workflow "$r" ci
  run "$STUBS" "$r"
  check "lint: a clean workflow records no findings" "0" "$(lint .error_count)"

  r="$(new_repo)"; add_broken_workflow "$r" broken
  run "$STUBS" "$r/apps/gadget"
  check "lint: records actionlint's findings" "1" "$(lint .error_count)"
  check "lint: findings carry the repo-relative file" ".github/workflows/broken.yml" "$(lint '.errors[0].file')"

  # Left to find the files itself, actionlint fails outright on these two.
  r="$(new_repo)"; add_broken_workflow "$r" broken; ln -s /nonexistent "$r/.github/workflows/dangling.yml"
  run "$STUBS" "$r"
  check "lint: a dangling symlink in workflows/ doesn't hide findings" "1" "$(lint .error_count)"

  r="$(mktemp -d)"; add_broken_workflow "$r" broken
  run "$STUBS_NOGIT" "$r"
  check "lint: no repo root still lints" "1" "$(lint .error_count)"

  # GitHub doesn't run workflows in subdirectories of .github/workflows.
  r="$(new_repo)"; add_workflow "$r" ci; add_broken_workflow "$r" broken
  mkdir -p "$r/.github/workflows/nested"; mv "$r/.github/workflows/broken.yml" "$r/.github/workflows/nested/"
  run "$STUBS" "$r"
  check "lint: skips files GitHub doesn't run (workflows/nested/)" "0" "$(lint .error_count)"

  # A run that fails outright records nothing rather than a clean zero.
  r="$(new_repo)"; add_workflow "$r" ci; printf 'self-hosted-runner: [\n' > "$r/.github/actionlint.yaml"
  run "$STUBS" "$r"
  check "lint: actionlint failing writes no .ci.lint" ".ci.dependencies.json,.ci.native.github_actions.json" "$(written)"
else
  echo "SKIP: lint cases (actionlint not installed)"
fi

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
